#!/usr/bin/env python3
"""DL3DV local WorldWarp benchmark. Imported by the standard-library pipeline CLI."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
N_FRAMES = 225  # 49 + 4 * (49 - 5)


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))


def build_plan(args):
    from pipelines import python_for
    if args.count < 1:
        raise ValueError('At least one scene is required; single-scene endpoint FID is unavailable')
    camera_policy = getattr(args, 'camera_intrinsics', 'upstream-mean')
    camera_source = getattr(args, 'camera_source', 'ttt3r')
    strength = getattr(args, 'strength', .8)
    geometry_source = getattr(args, 'geometry_source', 'rolling')
    if not 0 <= strength <= 1:
        raise ValueError('strength must be in [0,1]')
    audit_guidance = getattr(args, 'audit_guidance', False)
    if geometry_source == 'first-image' and audit_guidance:
        raise ValueError('First-image geometry writes explicit request records; --audit-guidance is for rolling geometry')
    out = Path(args.output).resolve()
    if out.exists():
        raise FileExistsError(f'Output already exists: {out}')
    inventory = json.loads(Path(args.manifest).read_text())
    entries = inventory['scenes']
    entries = sorted(entries, key=lambda s: s['scene_id'])[:args.count]
    if not entries or len(entries) != args.count:
        raise ValueError('Not enough scenes')
    if any(s['format'] != 'pixelsplat_torch' or s['frames'] < N_FRAMES for s in entries):
        raise ValueError('This benchmark adapter requires pixelSplat torch scenes with >=225 frames')
    for s in entries:
        if not Path(s['shard_path']).is_file():
            raise FileNotFoundError(s['shard_path'])
    steps = []
    for scene in entries:
        sid = scene['scene_id']; folder = out / sid[:12]
        for action in ('prepare', 'calibrate', 'generate', 'image-metrics', 'pose-metrics'):
            cmd = [python_for('worldwarp'), '-u', str(Path(__file__).resolve()), action,
                   '--output', str(folder), '--scene-id', sid, '--shard', scene['shard_path'],
                   '--dust3r-root', str(Path(args.dust3r_root).resolve())]
            cmd += ['--camera-intrinsics', camera_policy]
            cmd += ['--camera-source', camera_source]
            cmd += ['--strength', str(strength)]
            cmd += ['--geometry-source', geometry_source]
            if audit_guidance:
                cmd += ['--audit-guidance']
            steps.append(dict(name=f'{sid[:12]}_{action}', environment='worldwarp', command=cmd))
    steps.append(dict(name='report', environment='worldwarp', command=[python_for('worldwarp'), '-u',
        str(Path(__file__).resolve()), 'report', '--output', str(out)]))
    return dict(schema_version=1, pipeline='ww-dl3dv-benchmark',
        method='worldwarp', method_label=(f'WorldWarp / {camera_policy}' if camera_source=='ttt3r' else 'WorldWarp / dataset-camera diagnostic') + (f' / strength {strength:g} tuning' if strength != .8 else '') + (' / first-image geometry diagnostic' if geometry_source=='first-image' else ''),
        pipeline_definition=dict(id='ww-dl3dv-benchmark', kind='benchmark', environments=['worldwarp']),
        inputs=entries, source_manifest=str(Path(args.manifest).resolve()),
        selection_description=inventory.get('selection_description',
            '在生成前按本地清单 scene ID 排序固定选出，没有依据结果筛选。'),
        output=str(out), gpu=args.gpu, prompt='',
        parameters=dict(width=720, height=480, chunk_frames=49, overlap=5, chunks=5,
            delivered_frames=N_FRAMES, strength=strength, sampling_steps=50, gs_iterations=500, cfg=5, seed=32,
            dust3r_root=str(Path(args.dust3r_root).resolve()),
            endpoint_indices_zero_based=[49,199], conditioning_cameras=('TTT3R reference video (§7)' if camera_source=='ttt3r' else 'Dataset calibrated cameras, translation units fitted to reference TTT3R; diagnostic protocol'),
            camera_intrinsics_policy=camera_policy, audit_guidance=audit_guidance,
            camera_source=camera_source,
            geometry_source=geometry_source,
            pose_ground_truth='DL3DV supplied calibrated cameras', selection='first scene IDs in sorted local inventory'),
        steps=steps, notes=[f'Local {len(entries)}-scene protocol, not an official WorldWarp test split.',
            'Reference RGB beyond frame 0 is used only for reference camera extraction and scoring.',
            'Source images are 480x270; center crop and upscale to 720x480.',
            'Paper does not publish exact sampling, LPIPS backbone or pose reconstruction settings.'])


def prepare_reference_intrinsics(k, width, height, policy):
    """Match upstream reference-video K handling without mutating raw estimates."""
    import numpy as np
    result = np.array(k, copy=True)
    if policy == 'legacy-per-frame':
        return result
    if policy != 'upstream-mean':
        raise ValueError(f'Unknown intrinsics policy: {policy}')
    result[:, 0, 2] = width / 2
    result[:, 1, 2] = height / 2
    return np.repeat(result.mean(axis=0, keepdims=True), len(result), axis=0)


def dataset_camera_unit_scale(dataset_poses, reference_poses):
    """Fit only a positive translation unit scalar, never rotations or frame timing."""
    import numpy as np
    d = np.linalg.inv(dataset_poses[0]) @ dataset_poses
    r = np.linalg.inv(reference_poses[0]) @ reference_poses
    x, y = d[:, :3, 3], r[:, :3, 3]
    denominator = float(np.sum(x*x))
    if denominator < 1e-12:
        raise ValueError('Stationary dataset trajectory cannot determine a depth-unit scale')
    scale = float(np.sum(x*y) / denominator)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Invalid positive camera unit scale')
    d[:, :3, 3] *= scale
    return d, scale


def conditioning_path(folder):
    path = folder/'conditioning_cameras.npz'
    return path if path.is_file() else folder/'reference_ttt3r_cameras.npz'


def decode_cameras(cameras, width, height):
    import numpy as np
    n = len(cameras)
    k = np.tile(np.eye(3), (n,1,1))
    k[:,0,0], k[:,1,1] = cameras[:,0]*width, cameras[:,1]*height
    k[:,0,2], k[:,1,2] = cameras[:,2]*width, cameras[:,3]*height
    w2c = np.tile(np.eye(4), (n,1,1)); w2c[:,:3] = cameras[:,6:].reshape(n,3,4)
    c2w = np.linalg.inv(w2c)
    return np.linalg.inv(c2w[0]) @ c2w, k


def crop_transform(width, height, target_width=720, target_height=480):
    import numpy as np
    scale = max(target_width/width, target_height/height)
    rw, rh = int(width*scale), int(height*scale)
    x, y = (rw-target_width)//2, (rh-target_height)//2
    # OpenCV resize maps pixel centers: (u+.5)*scale-.5.
    a = np.array([[rw/width,0,(rw/width-1)/2-x],
                  [0,rh/height,(rh/height-1)/2-y], [0,0,1]])
    return (rw,rh,x,y), a


def prepare(args):
    import io
    import cv2
    import numpy as np
    import torch
    from PIL import Image
    out = args.output; out.mkdir(parents=True, exist_ok=False)
    scenes = torch.load(args.shard, map_location='cpu', weights_only=True)
    scene = next(s for s in scenes if s['key'] == args.scene_id)
    timestamps = scene['timestamps'].numpy()
    order = np.argsort(timestamps, kind='stable')[:N_FRAMES]
    if len(np.unique(timestamps[order])) != N_FRAMES:
        raise ValueError('Duplicate frame timestamps')
    gt = out/'gt'; gt.mkdir()
    native_sizes = []
    for i, source in enumerate(order):
        im = np.array(Image.open(io.BytesIO(scene['images'][source].numpy().tobytes())).convert('RGB'))
        h,w = im.shape[:2]; native_sizes.append([w,h])
        (rw,rh,x,y), a = crop_transform(w,h)
        frame = cv2.resize(im,(rw,rh),interpolation=cv2.INTER_LANCZOS4)[y:y+480,x:x+720]
        Image.fromarray(frame).save(gt/f'{i:05d}.png')
    if any(s != native_sizes[0] for s in native_sizes):
        raise ValueError('Varying image sizes are not supported')
    c2w, k = decode_cameras(scene['cameras'][order].numpy(), *native_sizes[0])
    k = a @ k
    np.savez_compressed(out/'dataset_cameras.npz', c2w=c2w.astype('float32'),
        intrinsics=k.astype('float32'), source_indices=order, source_timestamps=timestamps[order], image_transform=a)
    dump(out/'data.json', dict(scene_id=args.scene_id, shard=str(args.shard), native_size=native_sizes[0],
        prepared_size=[720,480], frames=N_FRAMES, source_indices=order.tolist(),
        timestamps=timestamps[order].tolist(), frame_numbering='First source image is frame 1 (index 0).',
        crop_transform=a.tolist(), camera_convention='OpenCV c2w relative to first frame',
        interpolation='OpenCV Lanczos4 resize followed by integer center crop'))


def setup_worldwarp():
    sys.path.insert(0, str(ROOT/'WorldWarp'))
    os.chdir(ROOT/'WorldWarp')


def calibrate(args):
    import numpy as np
    import torch
    from PIL import Image
    setup_worldwarp()
    from pose_control import TTT3RInference, seed_everything
    seed_everything(32)
    model = TTT3RInference(str(ROOT/'WorldWarp/src/ttt3r/cut3r_512_dpt_4_64.pth'), device='cuda')
    images = np.stack([np.array(Image.open(p)) for p in sorted((args.output/'gt').glob('*.png'))])
    tensor = torch.from_numpy(images).permute(0,3,1,2).float().div_(255).unsqueeze(0)
    started = time.monotonic()
    depth, poses, k = model.inference(tensor)
    poses = poses[0].cpu().numpy(); poses = np.linalg.inv(poses[0]) @ poses
    raw_k = k[0].cpu().numpy()
    policy = getattr(args, 'camera_intrinsics', 'upstream-mean')
    control_k = prepare_reference_intrinsics(raw_k, images.shape[2], images.shape[1], policy)
    np.savez_compressed(args.output/'reference_ttt3r_cameras.npz', c2w=poses, intrinsics=control_k)
    np.savez_compressed(args.output/'reference_ttt3r_raw_cameras.npz', c2w=poses, intrinsics=raw_k)
    source = getattr(args, 'camera_source', 'ttt3r')
    unit_scale = None
    control_poses = poses
    if source == 'dataset-calibrated':
        with np.load(args.output/'dataset_cameras.npz') as dataset:
            control_poses, unit_scale = dataset_camera_unit_scale(dataset['c2w'].astype('float64'), poses.astype('float64'))
            control_poses = control_poses.astype('float32')
            control_k = dataset['intrinsics']
    np.savez_compressed(args.output/'conditioning_cameras.npz', c2w=control_poses, intrinsics=control_k)
    # These depths are diagnostic reference observations, NEVER generation inputs.
    np.save(args.output/'reference_ttt3r_depth_DIAGNOSTIC_ONLY.npy', depth[0].cpu().numpy().astype('float16'))
    dump(args.output/'calibration.json', dict(seconds=time.monotonic()-started,
        uses_reference_rgb=True, generated_geometry_uses_reference_depth=False,
        camera_source='WorldWarp supplementary §7: TTT3R on reference video',
        camera_intrinsics_policy=policy, actual_control_camera_source=source,
        dataset_to_ttt3r_translation_scale=unit_scale,
        scale_uses='Paired camera translations only; no reference depths' if unit_scale is not None else None))


def generate(args):
    import imageio.v2 as imageio
    import numpy as np
    import torch
    from PIL import Image
    from omegaconf import OmegaConf
    setup_worldwarp()
    import pose_control as pc
    from chunk_trajectory import slice_chunk_trajectory
    out = args.output/'generation'; out.mkdir()
    cfg = OmegaConf.create(OmegaConf.to_container(pc.CONFIG, resolve=True))
    cfg.experiment.output_root = str(out/'artifacts'); cfg.experiment.seed = 32
    cfg.loop_params.n_chunks = 5; cfg.loop_params.output_fps = 30
    cfg.inference_params.update(n_frames=49, context_frames=1, context_frames_2nd=5,
        width=720, height=480, minxs=round(1-getattr(args, 'strength', .8), 10), num_gs_iterations=500, sampling_timesteps=50, guidance_scale=5)
    cfg.camera_pose_control.enabled = False
    pc.seed_everything(32)
    map_method = getattr(args, 'map_method', None)
    if map_method:
        from worldwarp_rolling_benchmark import generator_class
        generator = generator_class(pc)(cfg)
    else:
        generator = pc.WanVideoGenerator(cfg)
    generator._load_models()
    if getattr(args, 'audit_guidance', False) or getattr(args, 'geometry_source', 'rolling') == 'first-image':
        from worldwarp_benchmark_audit import verify_loaded_checkpoint
        verify_loaded_checkpoint(generator, out)
    generator._init_captioner(is_vl=True)
    if generator.caption_model is None:
        raise RuntimeError('Paper VLM captioner failed to load')
    trajectory = np.load(conditioning_path(args.output))
    poses = torch.from_numpy(trajectory['c2w']).unsqueeze(0).to(generator.device)
    intrinsics = torch.from_numpy(trajectory['intrinsics']).unsqueeze(0).to(generator.device)
    first = np.array(Image.open(args.output/'gt/00000.png'))
    current = np.repeat(first[None],49,axis=0)
    first_geometry_video = torch.from_numpy(current.copy()).permute(0,3,1,2).float().div(255).unsqueeze(0)
    original_preprocess, original_save = pc.preprocess_video_from_path, pc.imageio.mimsave
    original_warper = pc.batch_warp_frames_via_3dgs
    if getattr(args, 'geometry_source', 'rolling') == 'first-image':
        def first_image_warp(source_ids, target_ids, video, local_poses, local_k, model, *a, **kw):
            # Target indices of every chunk remain the exact original global trajectory.
            kw['is_first_chunk'] = True
            record = out/'first_image_geometry_requests'
            record.mkdir(exist_ok=True)
            np.savez_compressed(record/f'chunk_{idx:03d}.npz',
                source_frame_ids=np.array([0]),target_frame_ids=np.arange(idx*44,idx*44+49),
                c2w=trajectory['c2w'],intrinsics=trajectory['intrinsics'])
            return original_warper(torch.zeros((1,1),dtype=torch.long,device=video.device),
                torch.arange(idx*44,idx*44+49,device=video.device)[None],
                first_geometry_video.to(video.device),poses,intrinsics,model,*a,**kw)
        pc.batch_warp_frames_via_3dgs = first_image_warp
    bridge = None
    if getattr(args, 'guidance_dir', None):
        from worldwarp_hybrid_benchmark import FixedGameGuidance
        bridge = FixedGameGuidance(args.guidance_dir, trajectory, out)
        pc.batch_warp_frames_via_3dgs = bridge.warp
    elif map_method:
        from worldwarp_rolling_benchmark import RollingGuidance
        bridge = RollingGuidance(map_method, trajectory, args.output)
        pc.batch_warp_frames_via_3dgs = bridge.warp
    captured = {}
    def preprocess(*a, **kw):
        return torch.from_numpy(current.copy()).permute(0,3,1,2).float()/255
    def save(path, frames, *a, **kw):
        if Path(path).parent == Path(generator.pm.dirs['chunks']):
            captured['frames'] = np.asarray(frames).copy()
        return original_save(path, frames, *a, **kw)
    pc.preprocess_video_from_path, pc.imageio.mimsave = preprocess, save
    auditor = None
    if getattr(args, 'audit_guidance', False):
        if getattr(args, 'geometry_source', 'rolling') != 'rolling':
            raise ValueError('First-image diagnostic uses its own request records; do not combine with --audit-guidance')
        if bridge is not None:
            raise ValueError('Guidance audit currently supports original WorldWarp only')
        from worldwarp_benchmark_audit import GuidanceAudit
        auditor = GuidanceAudit(out/'guidance_audit', generator.ttt3r, pc.batch_warp_frames_via_3dgs)
        pc.batch_warp_frames_via_3dgs = auditor.warp
    gen = args.output/'generated'; gen.mkdir()
    started = time.monotonic(); report = dict(status='running', chunks=[], frames=0)
    torch.cuda.reset_peak_memory_stats()
    # This source clip contains copies of ONLY the first image. Later captions see generated history.
    source = out/'initial_image_repeated.mp4'
    original_save(source, current, fps=30)
    previous = str(source)
    try:
        for idx in range(5):
            if auditor is not None:
                auditor.chunk = idx
            if bridge is not None:
                bridge.chunk = idx
            context = 1 if idx == 0 else 5
            cp,ck = slice_chunk_trajectory(poses,intrinsics,idx,49,5)
            begin = time.monotonic()
            previous = generator.run_inference_chunk(idx, previous, cp, ck, context, idx==0)
            current = captured.pop('frames')
            assert current.shape == (49,480,720,3)
            for frame in current[0 if idx==0 else 5:]:
                Image.fromarray(frame).save(gen/f'{report["frames"]:05d}.png')
                report['frames'] += 1
            chunk_report=dict(index=idx, seconds=time.monotonic()-begin, path=previous)
            if map_method:
                import hashlib
                chunk_report['decoded_frame_sha256']=[hashlib.sha256(frame.tobytes()).hexdigest() for frame in current]
            report['chunks'].append(chunk_report)
            dump(out/'report.json',report)
            torch.cuda.empty_cache()
    finally:
        pc.preprocess_video_from_path, pc.imageio.mimsave = original_preprocess, original_save
        pc.batch_warp_frames_via_3dgs = original_warper
        if auditor is not None:
            auditor.close()
    assert report['frames'] == N_FRAMES
    for name, folder in [('generated',gen),('ground_truth',args.output/'gt')]:
        with imageio.get_writer(args.output/f'{name}.mp4', fps=30, codec='libx264', quality=9, macro_block_size=1) as writer:
            for p in sorted(folder.glob('*.png')):
                writer.append_data(np.array(Image.open(p)))
    report.update(status='complete', seconds=time.monotonic()-started,
        geometry_source=getattr(args, 'geometry_source', 'rolling'),
        peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
        output_video=str(args.output/'generated.mp4'), measurement_pixels='Lossless pre-video-encoding PNG')
    if bridge is not None:
        if len(bridge.calls) != 5:
            raise RuntimeError('Expected five actual geometry bridge calls')
        if map_method:
            report.update(method=map_method, method_label=bridge.label+' / '+bridge.variant,
                geometry='Rolling MapAnything + '+bridge.backend,game_used=False,
                ttt3r_model_loaded_in_generator=False,first_image_ttt3r_scale_calibration=True,
                geometry_bridge_calls=bridge.calls,generated_history_updates_geometry=True,
                historical_classroom_exact_config=False)
        else:
            report.update(method='map-game-ww', geometry='Single fixed GaME scene from first-image MapAnything',
                          geometry_bridge_calls=bridge.calls, generated_history_updates_geometry=False,
                          historical_classroom_B_exact_config=False)
    dump(out/'report.json',report)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare','calibrate','generate','image-metrics','pose-metrics','report'])
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--scene-id'); p.add_argument('--shard',type=Path)
    p.add_argument('--dust3r-root',type=Path,default=Path('/data4/sumai/eval_tools/dust3r'))
    p.add_argument('--guidance-dir',type=Path)
    p.add_argument('--map-method',choices=['map-ww-gs','map-ww-anchor-gs','map-ww-anchor-points'])
    p.add_argument('--camera-intrinsics',choices=['upstream-mean','legacy-per-frame'],default='upstream-mean')
    p.add_argument('--audit-guidance',action='store_true')
    p.add_argument('--strength', type=float, default=.8)
    p.add_argument('--geometry-source',choices=['rolling','first-image'],default='rolling')
    p.add_argument('--camera-source',choices=['ttt3r','dataset-calibrated'],default='ttt3r')
    a = p.parse_args(); a.output = a.output.resolve()
    if a.action in ('prepare','calibrate','generate'):
        globals()[a.action](a)
    else:
        from worldwarp_benchmark_metrics import image_metrics, pose_metrics, make_report
        {'image-metrics':image_metrics,'pose-metrics':pose_metrics,'report':make_report}[a.action](a)


if __name__ == '__main__':
    main()
