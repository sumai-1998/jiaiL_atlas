#!/usr/bin/env python3
"""MapAnything -> fixed GaME -> WorldWarp on the existing DL3DV benchmark grid.

The reference trajectory is copied exactly. Only the input image is used for
MapAnything geometry and a one-scalar TTT3R depth-unit calibration. No held-out
depth, RGB, or baseline generated images enter geometry or diffusion.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from worldwarp_benchmark import ROOT, N_FRAMES, dump


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def build_plan(args):
    if args.count < 2:
        raise ValueError('Paired GaME/F/G/H benchmarks currently require at least two scenes')
    from pipelines import python_for
    from worldwarp_benchmark import build_plan as original_plan
    plan = original_plan(args)
    sources = {}
    if not args.baseline_runs:
        raise ValueError('map-game-ww benchmark requires --baseline-runs for exact paired comparison')
    for directory in args.baseline_runs:
        directory = Path(directory).resolve()
        status = json.loads((directory/'status.json').read_text())
        summary = json.loads((directory/'metrics_summary.json').read_text())
        if status['status'] != 'complete' or summary['status'] != 'complete':
            raise ValueError(f'Baseline is incomplete: {directory}')
        if status['pipeline'] != 'ww-dl3dv-benchmark':
            raise ValueError('Comparison requires original WorldWarp baseline runs')
        if summary['parameters'].get('camera_source','ttt3r') != 'ttt3r':
            raise ValueError('Paired adapters currently require a TTT3R-camera baseline, not the calibrated-camera diagnostic')
        for key in ('width','height','chunks','chunk_frames','overlap','strength',
                    'sampling_steps','gs_iterations','cfg','seed','delivered_frames'):
            if summary['parameters'][key] != plan['parameters'][key]:
                raise ValueError(f'Baseline protocol mismatch: {key}')
        for scene in summary['scenes']:
            sid = scene['scene_id']
            if sid in sources:
                raise ValueError(f'Duplicate baseline scene: {sid}')
            sources[sid] = directory/scene['folder']
    steps = []
    def add(sid, name, env, script, *argv):
        steps.append(dict(name=f'{sid[:12]}_{name}', environment=env,
                          command=[python_for(env),'-u',str(ROOT/'scripts'/script), *map(str,argv)]))
    for scene in plan['inputs']:
        sid = scene['scene_id']
        if sid not in sources:
            raise ValueError(f'Selected scene is absent from baseline: {sid}')
        base = sources[sid]
        for name in ('data.json','gt/00000.png','reference_ttt3r_cameras.npz','dataset_cameras.npz',
                     'image_metrics.json','pose_metrics.json','inception_features.npz'):
            if not (base/name).is_file():
                raise FileNotFoundError(base/name)
        if json.loads((base/'data.json').read_text())['scene_id'] != sid:
            raise ValueError('Baseline scene identity mismatch')
        folder = Path(plan['output'])/sid[:12]
        scene['baseline_scene_dir'] = str(base)
        trajectory = folder/'reference_ttt3r_cameras.npz'
        add(sid,'prepare','worldwarp','worldwarp_hybrid_benchmark.py','prepare',
            '--output',folder,'--baseline-scene',base)
        add(sid,'mapanything','mapanything','mapanything_calibrated_rgbd.py',
            '--image',folder/'gt/00000.png','--trajectory',trajectory,'--output',folder/'mapanything')
        add(sid,'scale','worldwarp','worldwarp_hybrid_benchmark.py','scale','--output',folder)
        add(sid,'game-fit','game','fuse_geometry_game.py','--rgbd',folder/'geometry/posed_rgbd.npz',
            '--output',folder/'scene','--max-views',1,'--max-width',720,'--iterations',500)
        add(sid,'game-render','game','game_render_trajectory.py','--scene',folder/'scene',
            '--rgbd',folder/'geometry/posed_rgbd.npz','--trajectory',trajectory,
            '--output',folder/'guidance','--motion-mode','se3')
        for action in ('generate','image-metrics','pose-metrics'):
            tail = ['--guidance-dir',folder/'guidance'] if action=='generate' else []
            add(sid,action,'worldwarp','worldwarp_benchmark.py',action,'--output',folder,
                '--dust3r-root',args.dust3r_root,*tail)
    steps.append(dict(name='report',environment='worldwarp',command=[python_for('worldwarp'),'-u',
        str(ROOT/'scripts/worldwarp_benchmark.py'),'report','--output',plan['output']]))
    plan.update(pipeline='map-game-ww-dl3dv-benchmark',
        pipeline_definition=dict(id='map-game-ww-dl3dv-benchmark',kind='benchmark',
                                 environments=['worldwarp','mapanything','game']),steps=steps,
        baseline_runs=[str(Path(p).resolve()) for p in args.baseline_runs],
        method='map-game-ww', method_label='MapAnything + GaME + WorldWarp')
    plan['parameters'].update(method='map-game-ww',context_frames=1,context_frames_2nd=5,
        camera_intrinsics_policy='copied_from_baseline',camera_source='ttt3r',audit_guidance=False,
        game_warmup_iterations=50,game_seed=0,game_fit_width=720,
        scene_update='Fixed first-image scene; no generated-history geometry updates',
        scale_calibration='Median pixelwise ratio: first-image-only TTT3R depth / MapAnything depth',
        visibility='Native GaME alpha for full SE3; no rotation-only homography clipping')
    plan['notes'] += ['Three-project architecture adapted to benchmark controls, not historical B .6/ctx1.',
        'Reference RGB-D beyond the first input image is not used for geometry or scale calibration.',
        'Reuse exact baseline PNG and camera bytes; fit GaME once at full 720x480.',
        'Qwen caption policy matches baseline; later captions may differ with generated history.']
    return plan


def prepare(args):
    import numpy as np
    base = args.baseline_scene.resolve()
    out = args.output
    out.mkdir(parents=True,exist_ok=False)
    (out/'gt').mkdir()
    provenance = {}
    paths = [f'gt/{i:05d}.png' for i in range(N_FRAMES)]
    paths += ['dataset_cameras.npz','reference_ttt3r_cameras.npz','data.json']
    for name in paths:
        src,dst = base/name,out/name
        shutil.copy2(src,dst)
        digest = sha256(src)
        if sha256(dst) != digest:
            raise RuntimeError(f'Copy checksum mismatch: {name}')
        provenance[name] = digest
    data = json.loads((out/'data.json').read_text())
    cam = np.load(out/'reference_ttt3r_cameras.npz')
    if cam['c2w'].shape != (225,4,4) or cam['intrinsics'].shape != (225,3,3):
        raise ValueError('Unexpected baseline camera shape')
    dump(out/'paired_input_provenance.json',dict(baseline_scene=str(base),
        scene_id=data['scene_id'],sha256=provenance,
        reference_depth_copied=False,baseline_generated_images_copied=False,
        geometry_image_indices=[0],camera_source='Unmodified baseline TTT3R reference trajectory'))


def depth_scale(source, target, valid):
    import numpy as np
    valid = valid & np.isfinite(source) & np.isfinite(target) & (source>0) & (target>0)
    if valid.sum()<100:
        raise ValueError('Insufficient valid pixels for single-image depth-unit calibration')
    scale = float(np.median(target[valid]/source[valid]))
    if not np.isfinite(scale) or scale<=0:
        raise ValueError('Invalid depth scale')
    return scale,valid


def scale(args):
    import numpy as np
    import torch
    from PIL import Image
    from worldwarp_benchmark import setup_worldwarp
    setup_worldwarp()
    from pose_control import TTT3RInference,seed_everything
    seed_everything(32)
    out = args.output
    rgb = np.array(Image.open(out/'gt/00000.png'))
    model = TTT3RInference(str(ROOT/'WorldWarp/src/ttt3r/cut3r_512_dpt_4_64.pth'),device='cuda')
    tensor = torch.from_numpy(rgb).permute(2,0,1).float().div(255)[None,None]
    with torch.inference_mode():
        depth,poses,k = model.inference(tensor)
    depth = depth[0,0].detach().float().cpu().numpy()
    package = dict(np.load(out/'mapanything/posed_rgbd.npz'))
    factor,valid = depth_scale(package['depth_z'][0],depth,package['valid'][0])
    geometry = out/'geometry';geometry.mkdir()
    np.savez_compressed(geometry/'first_image_ttt3r_scale_reference.npz',depth_z=depth,
                        c2w=poses.cpu().numpy(),intrinsics=k.cpu().numpy())
    package['depth_z'] = package['depth_z']*factor
    np.savez_compressed(geometry/'posed_rgbd.npz',**package)
    dump(geometry/'scale_calibration.json',dict(scale=factor,valid_pixels=int(valid.sum()),
        source='First real input image only, independently inferred by TTT3R',
        held_out_depth_used=False,geometry_shape='MapAnything; only a global scalar changes',
        median_ttt3r_depth=float(np.median(depth[valid])),
        median_scaled_map_depth=float(np.median(package['depth_z'][0][valid])),
        trajectory_changed=False))


def target_global_indices(chunk, target_ids):
    import numpy as np
    # Keep this helper CPU-only; no pose_control/model imports.
    if chunk not in range(5):
        raise ValueError('Benchmark has five chunks')
    start = 0 if chunk==0 else (chunk-1)*44
    expected = np.arange(49) if chunk==0 else np.arange(44,93)
    if not np.array_equal(target_ids,expected):
        raise ValueError('Unexpected native target window')
    return start+expected


class FixedGameGuidance:
    def __init__(self, directory, trajectory, output):
        import numpy as np
        self.directory=Path(directory);self.output=Path(output)
        self.rgb=np.load(self.directory/'warped_rgb.npy',mmap_mode='r')
        self.alpha=np.load(self.directory/'valid_alpha.npy',mmap_mode='r')
        self.trajectory=trajectory;self.calls=[];self.chunk=0
        if self.rgb.shape!=(225,480,720,3) or self.alpha.shape!=(225,480,720):
            raise ValueError('GaME guidance dimensions do not match the benchmark')
        rendered=np.load(self.directory/'trajectory.npz')
        for field in ('c2w','intrinsics'):
            np.testing.assert_array_equal(rendered[field],trajectory[field])

    def warp(self,source_ids,target_ids,video_tensor,camera_poses,intrinsics,ttt3r,**kwargs):
        import numpy as np
        import torch
        import pose_control as pc
        from chunk_trajectory import chunk_pose_bounds
        ids=target_global_indices(self.chunk,target_ids[0].detach().cpu().numpy())
        start,end=chunk_pose_bounds(self.chunk,49,5)
        cp=torch.from_numpy(self.trajectory['c2w'][start:end]).unsqueeze(0).to(camera_poses.device)
        ck=torch.from_numpy(self.trajectory['intrinsics'][start:end]).unsqueeze(0).to(intrinsics.device)
        relative=pc.get_relative_poses(cp,torch.zeros((1,1),dtype=torch.long,device=cp.device))
        torch.testing.assert_close(camera_poses,relative,atol=1e-6,rtol=1e-6)
        torch.testing.assert_close(intrinsics,ck,atol=0,rtol=0)
        expected_source=[0] if self.chunk==0 else list(range(44,49))
        if source_ids[0].tolist()!=expected_source or tuple(video_tensor.shape)!=(1,49,3,480,720):
            raise ValueError('Unexpected context input')
        rgb=np.array(self.rgb[ids],dtype=np.float32)
        alpha=np.array(self.alpha[ids],dtype=np.float32)
        if not np.isfinite(rgb).all() or not np.isfinite(alpha).all():
            raise RuntimeError('Non-finite fixed-scene guidance')
        self.calls.append(dict(chunk=self.chunk,global_target_indices=ids.tolist(),
            context_frames=len(expected_source),valid_fraction=float((alpha>=.5).mean()),
            worldwarp_ttt3r_geometry_inference=False,geometry_updates_from_generated_frames=False))
        dump(self.output/'geometry_bridge_calls.json',self.calls)
        print('GaME BENCHMARK BRIDGE:',self.calls[-1],flush=True)
        return (torch.from_numpy(rgb).permute(0,3,1,2)[None].to(video_tensor.device),
                torch.from_numpy(alpha)[None,:,None].to(video_tensor.device),None)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','scale'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline-scene',type=Path)
    args=parser.parse_args();args.output=args.output.resolve()
    globals()[args.action](args)


if __name__=='__main__':
    main()
