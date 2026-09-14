#!/usr/bin/env python3
"""Three GaME-free, rolling MapAnything + WorldWarp combinations."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'WorldWarp'))


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--variant', choices=['rolling_gs', 'anchor_gs', 'anchor_points'], required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--context-frames', type=int, default=5)
    parser.add_argument('--first-rgbd', type=Path)
    args, remainder = parser.parse_known_args()
    import cv2
    import numpy as np
    import torch
    from PIL import Image
    import pose_control as pc
    import generate_worldwarp_rotation as runner
    from generate_worldwarp_hybrid_context import context_window
    from worldwarp_map_geometry import render_geometry, select_history

    cv2.setNumThreads(4)
    torch.set_num_threads(4)
    baseline = args.baseline.resolve()
    traj = np.load(baseline/'requested_camera_trajectory.npz')
    reference = np.array(Image.open(baseline/'input_prepared.png').convert('RGB'))
    from pipeline_reference import reference_captions
    captions = reference_captions(baseline)
    anchor = args.variant.startswith('anchor_')
    backend = 'points' if args.variant == 'anchor_points' else 'gs'
    original_class, original_warper = pc.WanVideoGenerator, pc.batch_warp_frames_via_3dgs
    instances = []

    class MapGenerator(original_class):
        def __init__(self, cfg):
            cfg.inference_params.context_frames_2nd = args.context_frames
            super().__init__(cfg)
            self.calls = []
            self.output = Path(cfg.experiment.output_root).parent
            pc.batch_warp_frames_via_3dgs = self.geometry_warp
            instances.append(self)

        def _load_models(self):
            # Keep the native WorldWarp VAE, diffusion checkpoint, scheduler and
            # text encoder. Geometry is exclusively supplied by MapAnything.
            print('Loading WorldWarp diffusion models; geometry backend is MapAnything.', flush=True)
            self.vae = pc.AutoencoderKLWan.from_pretrained(self.cfg.paths.base_model_path,
                subfolder='vae', torch_dtype=torch.float32).to(self.device).eval()
            self.transformer = pc.WanTransformer3DModel.from_pretrained(self.cfg.paths.base_model_path,
                subfolder='transformer', torch_dtype=self.dtype)
            checkpoint = torch.load(self.cfg.paths.finetuned_checkpoint_path, map_location='cpu', weights_only=False)
            self.transformer.load_state_dict(checkpoint, strict=True)
            del checkpoint
            self.transformer = self.transformer.to(self.device).eval()
            self.scheduler = pc.FlowMatchEulerDiscreteScheduler(shift=5)
            self.text_pipe = pc.WanPipeline.from_pretrained(self.cfg.paths.base_model_path,
                vae=None, transformer=None, torch_dtype=self.dtype).to(self.device)
            self.video_processor = pc.VideoProcessor(vae_scale_factor=self.cfg.model_params.latent_downsampling_factor[1])
            self.ttt3r = None

        def _init_captioner(self, is_vl=True):
            self.caption_model = 'cached_baseline_captions'

        def get_caption(self, **kwargs):
            return captions[self.current_chunk]

        def geometry_warp(self, source_ids, target_ids, video_tensor, camera_poses,
                          intrinsics, ttt3r, **kwargs):
            started = time.monotonic()
            chunk = self.current_chunk
            window = self.window
            count, context = len(window['source']), window['context']
            assert video_tensor.shape[1] == count and ttt3r is None
            offset = 0 if chunk == 0 else count-context
            torch.testing.assert_close(target_ids[0], torch.arange(offset, offset+count, device=target_ids.device))
            expected = traj['c2w'][window['poses']].astype(np.float64)
            expected = np.linalg.inv(expected[0]) @ expected
            np.testing.assert_allclose(camera_poses[0].cpu().numpy(), expected, atol=1e-6, rtol=1e-6)
            np.testing.assert_array_equal(intrinsics[0].cpu().numpy(), traj['intrinsics'][window['poses']])
            selected = select_history(chunk, anchor)
            source_images = []
            for frame_id, observed, local in selected:
                if observed:
                    source_images.append(reference.copy())
                else:
                    # Exclude the repeated prefix used only to extend the VAE
                    # target window. Every selected frame is real generated history.
                    frame = video_tensor[0, local+window['extra_prefix']].permute(1, 2, 0)
                    source_images.append(np.rint(frame.cpu().numpy()*255).clip(0, 255).astype(np.uint8))
            source_images = np.stack(source_images)
            ids = np.array([r[0] for r in selected], dtype=np.int64)
            observed = np.array([r[1] for r in selected], dtype=bool)
            geometry_dir = self.output/'geometry'/f'chunk_{chunk:03d}'
            geometry_dir.mkdir(parents=True, exist_ok=False)
            input_path = geometry_dir/'mapanything_input.npz'
            np.savez_compressed(input_path, rgb=source_images, frame_ids=ids, observed=observed,
                                c2w=traj['c2w'][ids], intrinsics=traj['intrinsics'][ids])
            for i, frame in enumerate(source_images):
                Image.fromarray(frame).save(geometry_dir/f'source_{i:02d}_global_{ids[i]:03d}.png')
            rgbd_path = geometry_dir/'posed_rgbd.npz'
            if chunk == 0 and args.first_rgbd:
                import shutil
                shared = np.load(args.first_rgbd)
                for key in ('rgb', 'frame_ids', 'observed', 'c2w', 'intrinsics'):
                    np.testing.assert_array_equal(shared[key], np.load(input_path)[key])
                shutil.copy2(args.first_rgbd, rgbd_path)
                shutil.copy2(args.first_rgbd.with_suffix('.json'), rgbd_path.with_suffix('.json'))
                geometry_source = str(args.first_rgbd.resolve())
            else:
                env = os.environ.copy()
                env.update(TORCH_HOME=str(ROOT/'.cache/torch_geometry'), HF_HOME=str(ROOT/'hf_cache'),
                    HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                    PYTHONNOUSERSITE='1', OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4')
                env['PYTHONPATH'] = str(ROOT/'MapAnything') + os.pathsep + env.get('PYTHONPATH', '')
                command = [os.environ.get('GIL_MAPANYTHING_PYTHON', str(ROOT/'conda_envs/mapanything/bin/python')),
                           str(ROOT/'scripts/mapanything_worldwarp_rgbd.py'),
                           '--input', str(input_path), '--output', str(rgbd_path)]
                (geometry_dir/'mapanything_command.json').write_text(json.dumps(command, indent=2))
                print(f'Chunk {chunk+1}: MapAnything estimates {len(ids)} source views {ids.tolist()}', flush=True)
                torch.cuda.empty_cache()
                with (geometry_dir/'mapanything.log').open('w') as log:
                    subprocess.run(command, env=env, check=True, stdout=log, stderr=subprocess.STDOUT)
                geometry_source = str(rgbd_path)
            targets = window['target']
            rgb, alpha, render_report = render_geometry(rgbd_path, traj['c2w'][targets],
                traj['intrinsics'][targets], backend, geometry_dir,
                iterations=self.cfg.inference_params.num_gs_iterations, device=self.device)
            for index in (0, len(targets)//2, len(targets)-1):
                Image.fromarray(np.rint(rgb[index]*255).astype(np.uint8)).save(geometry_dir/f'warp_{targets[index]:03d}.png')
                Image.fromarray(np.rint(alpha[index]*255).astype(np.uint8)).save(geometry_dir/f'valid_{targets[index]:03d}.png')
            row = dict(chunk=chunk, variant=args.variant, backend=backend,
                source_global_frames=ids.tolist(), source_observed=observed.tolist(),
                source_image_sha256=[hashlib.sha256(x.tobytes()).hexdigest() for x in source_images],
                geometry_source=geometry_source, mapanything_report=str(rgbd_path.with_suffix('.json')),
                render_report=render_report, context_frames=context, raw_frame_count=len(targets),
                raw_target_frames=[targets[0], targets[-1]], actual_context_global_frames=targets[:context],
                exported_target_frames=[chunk*80, chunk*80+80], extra_prefix_discarded=window['extra_prefix'],
                caption_sha256=hashlib.sha256(captions[chunk].encode()).hexdigest(),
                elapsed_seconds=time.monotonic()-started)
            self.calls.append(row)
            (self.output/'geometry_bridge_calls.json').write_text(json.dumps(self.calls, indent=2))
            print('MAPANYTHING + WORLDWARP GEOMETRY:', json.dumps({k:v for k,v in row.items() if k!='render_report'}), flush=True)
            return (torch.from_numpy(rgb).permute(0, 3, 1, 2)[None].to(video_tensor.device),
                    torch.from_numpy(alpha)[None, :, None].to(video_tensor.device), None)

        def run_inference_chunk(self, chunk_idx, input_video_path, chunk_poses,
                                chunk_intrinsics, context_frames, is_first_chunk, **kwargs):
            self.current_chunk = chunk_idx
            self.window = context_window(chunk_idx, args.context_frames)
            ids = self.window['poses']
            cp = torch.from_numpy(traj['c2w'][ids]).unsqueeze(0).to(self.device)
            ck = torch.from_numpy(traj['intrinsics'][ids]).unsqueeze(0).to(self.device)
            original_preprocess, original_save = pc.preprocess_video_from_path, pc.imageio.mimsave
            extra = self.window['extra_prefix']

            def prepare(*a, **kw):
                video = original_preprocess(*a, **kw)
                assert video.shape[0] == 81
                return torch.cat([video[:1].expand(extra, -1, -1, -1), video], dim=0) if extra else video

            def save(path, frames, *a, **kw):
                assert len(frames) == 81+extra
                if extra:
                    raw = Path(self.pm.exp_dir)/'raw_context_chunks'
                    raw.mkdir(exist_ok=True)
                    original_save(str(raw/f'chunk_{chunk_idx:03d}_{len(frames)}frames.mp4'), frames, *a, **kw)
                return original_save(path, frames[extra:], *a, **kw)

            pc.preprocess_video_from_path, pc.imageio.mimsave = prepare, save
            try:
                return super().run_inference_chunk(chunk_idx, input_video_path, cp, ck,
                    self.window['context'], is_first_chunk, **kwargs)
            finally:
                pc.preprocess_video_from_path, pc.imageio.mimsave = original_preprocess, original_save

    pc.WanVideoGenerator = MapGenerator
    sys.argv = [sys.argv[0]] + remainder
    try:
        runner.main()
        generator = instances[0]
        assert len(generator.calls) == 4
        output = generator.output
        report = json.loads((output/'report.json').read_text())
        report.update(variant=args.variant, context_frames_2nd=args.context_frames,
            raw_chunk_frames=[x['raw_frame_count'] for x in generator.calls],
            game_used=False, ttt3r_model_loaded=False, geometry_updates_from_generated_frames=True)
        (output/'report.json').write_text(json.dumps(report, indent=2))
        np.testing.assert_array_equal(reference, np.array(Image.open(output/'input_prepared.png')))
        for key in ('c2w', 'intrinsics', 'fps'):
            np.testing.assert_array_equal(np.load(output/'requested_camera_trajectory.npz')[key], traj[key])
        assert not any(name == 'game' or name.startswith('game.') for name in sys.modules)
        pipeline = dict(status='complete', variant=args.variant,
            pipeline=['MapAnything conditioned multi-view geometry',
                      'WorldWarp native 3DGS' if backend=='gs' else 'Bilinear point-cloud projection',
                      'WorldWarp ST-Diff'], game_used=False, ttt3r_model_loaded=False,
            geometry_updates_from_generated_frames=True, original_image_anchor=anchor,
            baseline_captions_reused=not (baseline/'reference.json').exists(),
            prepared_reference_used=(baseline/'reference.json').exists(), original_input_pixels_equal=True,
            original_camera_trajectory_equal=True, context_frames_2nd=args.context_frames,
            calls=generator.calls,
            camera_note='Requested cameras are held fixed; generated-frame camera motion is not measured ground truth.',
            geometry_note='Rolling recent-history reconstruction; anchor variants also include the original image. No persistent GaME map.',
            experiment_note='See this run config/plan for actual context, strength and seed. Historical F/G/H used ctx5, strength .6 and seed32; new inputs need not reproduce historical captions.')
        (output/'pipeline_report.json').write_text(json.dumps(pipeline, indent=2))
    finally:
        pc.WanVideoGenerator, pc.batch_warp_frames_via_3dgs = original_class, original_warper


if __name__ == '__main__':
    main()
