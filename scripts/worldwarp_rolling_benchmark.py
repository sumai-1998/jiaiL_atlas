"""F/G/H adapters for the paired 225-frame DL3DV benchmark (full SE3)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from worldwarp_benchmark import ROOT, dump
from worldwarp_hybrid_benchmark import target_global_indices

METHODS = {'map-ww-gs': ('F', 'rolling_gs', 'gs'),
           'map-ww-anchor-gs': ('G', 'anchor_gs', 'gs'),
           'map-ww-anchor-points': ('H', 'anchor_points', 'points')}


def select_sources(chunk, anchor):
    if chunk not in range(5):
        raise ValueError('Expected one of five benchmark chunks')
    if chunk == 0:
        return [(0, True, None)]
    start = (chunk - 1) * 44
    result = [(start + i, False, i) for i in (0, 12, 24, 36, 48)]
    return ([(0, True, None)] + [r for r in result if r[0] != 0]) if anchor else result


def build_plan(args):
    from pipelines import python_for
    from worldwarp_hybrid_benchmark import build_plan as paired_plan
    plan = paired_plan(args)  # Reuse strict baseline protocol/input validation.
    label, variant, backend = METHODS[args.method]
    retained = []
    for step in plan['steps']:
        if step['name'].endswith(('_game-fit', '_game-render')):
            continue
        if step['name'].endswith('_generate'):
            argv = step['command']
            pos = argv.index('--guidance-dir')
            step['command'] = argv[:pos] + ['--map-method', args.method]
        retained.append(step)
    plan.update(method=args.method, method_label=f'{label}: MapAnything + WorldWarp ({variant})',
        pipeline=args.method+'-dl3dv-benchmark',
        pipeline_definition=dict(id=args.method+'-dl3dv-benchmark', kind='benchmark',
                                 environments=['worldwarp','mapanything']), steps=retained)
    for key in ('game_warmup_iterations','game_seed','game_fit_width'):
        plan['parameters'].pop(key, None)
    plan['parameters'].update(method=args.method, variant=variant, geometry_backend=backend,
        scene_update='Re-estimate MapAnything from own generated history every chunk; no persistent map',
        geometry_keyframes_local=[0,12,24,36,48], original_image_anchor=label!='F', anchor_weight=2,
        scale_calibration='One fixed scalar from first-image-only TTT3R / MapAnything; applied to all chunks',
        scale_limitation='Window-dependent MapAnything scale drift is not additionally corrected',
        visibility=('Native GS rendered alpha times source depth-consistency mask, relative threshold .1'
                    if backend=='gs' else 'Per-source z-buffer 2% depth tolerance, bilinear coverage and weighted RGB fusion'),
        retention='compact: transient geometry removed after render; lossless PNG removed only after metric/report verification')
    plan['notes'] = [
        'F/G/H architecture adapted to baseline SE3, 225 frames and strength .8; not classroom .6 exact configuration.',
        'Exact baseline PNG/camera bytes; no held-out RGB/depth or baseline generated frames in geometry.',
        'Geometry keyframes (0,12,24,36,48) differ from five consecutive diffusion context frames (44..48).',
        'Only first-image scale calibration uses TTT3R; rolling geometry is exclusively MapAnything.',
        'Requested cameras retained downstream; generated history is not new real observation.',
        'Qwen captions follow own generated history as in baseline; later texts may differ.',
        'Original baseline and prior experiments will not be pruned.']
    return plan


def generator_class(pc):
    """Keep the same diffusion loader and caption policy, without a TTT3R model."""
    class MapGenerator(pc.WanVideoGenerator):
        def _load_models(self):
            import torch
            self.vae = pc.AutoencoderKLWan.from_pretrained(self.cfg.paths.base_model_path,
                subfolder='vae', torch_dtype=torch.float32).to(self.device).eval()
            self.transformer = pc.WanTransformer3DModel.from_pretrained(self.cfg.paths.base_model_path,
                subfolder='transformer', torch_dtype=self.dtype)
            state = torch.load(self.cfg.paths.finetuned_checkpoint_path, map_location='cpu', weights_only=False)
            self.transformer.load_state_dict(state, strict=True)
            del state
            self.transformer = self.transformer.to(self.device).eval()
            self.scheduler = pc.FlowMatchEulerDiscreteScheduler(shift=5)
            self.text_pipe = pc.WanPipeline.from_pretrained(self.cfg.paths.base_model_path,
                vae=None, transformer=None, torch_dtype=self.dtype).to(self.device)
            self.video_processor = pc.VideoProcessor(vae_scale_factor=self.cfg.model_params.latent_downsampling_factor[1])
            self.ttt3r = None
    return MapGenerator


class RollingGuidance:
    def __init__(self, method, trajectory, scene_output):
        import numpy as np
        from PIL import Image
        self.method = method
        self.label,self.variant,self.backend = METHODS[method]
        self.anchor = self.label != 'F'
        self.trajectory = trajectory
        self.scene = Path(scene_output)
        self.output = self.scene/'generation'
        self.reference = np.array(Image.open(self.scene/'gt/00000.png'))
        self.factor = json.loads((self.scene/'geometry/scale_calibration.json').read_text())['scale']
        self.calls = []; self.chunk = 0

    def warp(self, source_ids, target_ids, video_tensor, camera_poses, intrinsics, ttt3r, **kwargs):
        import numpy as np
        import torch
        from PIL import Image
        import pose_control as pc
        from chunk_trajectory import chunk_pose_bounds
        from pipelines import stage_env, python_for
        from worldwarp_map_geometry import render_geometry
        started = time.monotonic()
        targets = target_global_indices(self.chunk, target_ids[0].cpu().numpy())
        start,end = chunk_pose_bounds(self.chunk,49,5)
        poses = torch.from_numpy(self.trajectory['c2w'][start:end])[None].to(camera_poses.device)
        expected = pc.get_relative_poses(poses,torch.zeros((1,1),dtype=torch.long,device=poses.device))
        torch.testing.assert_close(camera_poses, expected, atol=1e-6, rtol=1e-6)
        np.testing.assert_array_equal(intrinsics[0].cpu().numpy(),self.trajectory['intrinsics'][start:end])
        context = [0] if self.chunk==0 else list(range(44,49))
        if source_ids[0].tolist()!=context or tuple(video_tensor.shape)!=(1,49,3,480,720) or ttt3r is not None:
            raise ValueError('Unexpected benchmark context or geometry model')
        selected = select_sources(self.chunk,self.anchor)
        images = np.stack([self.reference.copy() if observed else
            np.rint(video_tensor[0,local].permute(1,2,0).cpu().numpy()*255).clip(0,255).astype(np.uint8)
            for _,observed,local in selected])
        ids = np.array([r[0] for r in selected]); observed = np.array([r[1] for r in selected])
        folder = self.output/'geometry'/f'chunk_{self.chunk:03d}'
        folder.mkdir(parents=True,exist_ok=False)
        input_path = folder/'mapanything_input.npz'
        package = dict(rgb=images,frame_ids=ids,observed=observed,
                       c2w=self.trajectory['c2w'][ids],intrinsics=self.trajectory['intrinsics'][ids])
        np.savez_compressed(input_path,**package)
        rgbd_path = folder/'posed_rgbd.npz'
        if self.chunk==0:
            with np.load(self.scene/'geometry/posed_rgbd.npz') as loaded:
                data = dict(loaded)
            for key in ('rgb','c2w','intrinsics'):
                np.testing.assert_array_equal(data[key],package[key])
            data.update(frame_ids=ids,observed=observed)
            np.savez_compressed(rgbd_path,**data)
            map_source = 'First-image calibrated MapAnything prepared before generation'
        else:
            env = stage_env('mapanything',os.environ['CUDA_VISIBLE_DEVICES'])
            command = [python_for('mapanything'),'-u',str(ROOT/'scripts/mapanything_worldwarp_rgbd.py'),
                       '--input',str(input_path),'--output',str(rgbd_path)]
            dump(folder/'mapanything_command.json',command)
            torch.cuda.empty_cache()
            with (folder/'mapanything.log').open('w') as log:
                subprocess.run(command,env=env,cwd=ROOT,check=True,stdout=log,stderr=subprocess.STDOUT)
            with np.load(rgbd_path) as loaded:
                data = dict(loaded)
            data['depth_z'] = data['depth_z']*self.factor
            np.savez_compressed(rgbd_path,**data)
            map_source = 'Own generated history, plus original image for G/H'
        rgb,alpha,render = render_geometry(rgbd_path,self.trajectory['c2w'][targets],
            self.trajectory['intrinsics'][targets],self.backend,folder,iterations=500,device=video_tensor.device)
        for index in (0,24,48):
            Image.fromarray(np.rint(rgb[index]*255).astype(np.uint8)).save(folder/f'warp_{targets[index]:03d}.jpg',quality=90)
        row = dict(chunk=self.chunk,method=self.method,backend=self.backend,
            global_target_indices=targets.tolist(),context_frames=len(context),
            context_global_indices=targets[:len(context)].tolist(),source_global_frames=ids.tolist(),
            source_observed=observed.tolist(),source_local_indices=[r[2] for r in selected],
            source_image_sha256=[hashlib.sha256(x.tobytes()).hexdigest() for x in images],
            source='Only real first image and own generated history',map_source=map_source,
            scale=self.factor,scale_policy='Fixed first-image scalar for all windows',
            worldwarp_ttt3r_geometry_inference=False,game_used=False,
            geometry_updates_from_generated_frames=self.chunk>0,render_report=render,
            geometry_input_sha256=hashlib.sha256(input_path.read_bytes()).hexdigest(),
            elapsed_seconds=time.monotonic()-started)
        # These are run-owned, disposable geometry artifacts; RGB/alpha already reside in memory.
        removed=[]
        for name in ('mapanything_input.npz','posed_rgbd.npz','native_3dgs.pt','warped_rgb.npy','valid_alpha.npy'):
            path=folder/name
            if path.exists():
                removed.append(dict(file=name,bytes=path.stat().st_size));path.unlink()
        row['compact_removed_after_render']=removed
        self.calls.append(row);dump(self.output/'geometry_bridge_calls.json',self.calls)
        print('ROLLING MAP BENCHMARK BRIDGE:',json.dumps(row),flush=True)
        return (torch.from_numpy(rgb).permute(0,3,1,2)[None].to(video_tensor.device),
                torch.from_numpy(alpha)[None,:,None].to(video_tensor.device),None)
