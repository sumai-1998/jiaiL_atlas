#!/usr/bin/env python3
"""A larger real overlap inside WorldWarp, with the same 321-frame delivery grid."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "WorldWarp"))


def context_window(chunk_idx, context_frames):
    """Return source/pose/target global indices and the extra prefix to discard."""
    if chunk_idx not in range(4) or context_frames not in (1, 5, 9, 13, 17, 21, 25):
        raise ValueError("Four chunks and 1+4k context frames are required")
    if chunk_idx == 0:
        return dict(source=list(range(81)), poses=list(range(81)), target=list(range(81)),
                    context=1, extra_prefix=0)
    source_start = (chunk_idx-1)*80
    extra = context_frames-1
    # WorldWarp derives output length from the decoded source length. Its warper
    # is replaced here; only the actual final context frames enter VAE conditioning.
    # Padding the unused source prefix extends the target length without inventing
    # any history at the context boundary or re-encoding the source video.
    source = [source_start]*extra + list(range(source_start, source_start+81))
    target = list(range(chunk_idx*80-extra, chunk_idx*80+81))
    poses = source + target[context_frames:]
    assert poses[len(source)-context_frames:] == target
    assert source[-context_frames:] == target[:context_frames]
    return dict(source=source, poses=poses, target=target,
                context=context_frames, extra_prefix=extra)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--guidance-dir", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--context-frames", type=int, default=5)
    args, remainder = parser.parse_known_args()
    context_window(1, args.context_frames)
    guidance, baseline = args.guidance_dir.resolve(), args.baseline.resolve()
    import numpy as np
    import torch
    import pose_control as pc
    import generate_worldwarp_rotation as runner

    traj = np.load(guidance / "trajectory.npz")
    base_traj = np.load(baseline / "requested_camera_trajectory.npz")
    for field in ("c2w", "intrinsics", "fps"):
        np.testing.assert_array_equal(traj[field], base_traj[field])
    from pipeline_reference import reference_captions
    captions = reference_captions(baseline)
    original_class, original_warper = pc.WanVideoGenerator, pc.batch_warp_frames_via_3dgs
    instances = []

    class ContextGenerator(original_class):
        def __init__(self, cfg):
            cfg.inference_params.context_frames_2nd = args.context_frames
            super().__init__(cfg)
            self.guidance_rgb = np.load(guidance / "warped_rgb.npy", mmap_mode="r")
            self.guidance_alpha = np.load(guidance / "valid_alpha.npy", mmap_mode="r")
            assert self.guidance_rgb.shape == (321, 608, 480, 3)
            assert self.guidance_alpha.shape == (321, 608, 480)
            self.calls = []
            pc.batch_warp_frames_via_3dgs = self.geometry_warp
            instances.append(self)

        def _init_captioner(self, is_vl=True):
            self.caption_model = "cached_baseline_captions"

        def get_caption(self, **kwargs):
            return captions[self.current_chunk]

        def geometry_warp(self, source_ids, target_ids, video_tensor, camera_poses,
                          intrinsics, ttt3r, **kwargs):
            window = self.window
            n, context = len(window["source"]), window["context"]
            assert video_tensor.shape[1] == n
            start = 0 if self.current_chunk == 0 else n-context
            torch.testing.assert_close(target_ids[0], torch.arange(start, start+n, device=target_ids.device))
            torch.testing.assert_close(source_ids[0], torch.arange(start, start+context, device=source_ids.device))
            poses = torch.from_numpy(traj["c2w"][window["poses"]]).to(camera_poses.device)
            relative = pc.get_relative_poses(poses.unsqueeze(0), torch.zeros((1,1), dtype=torch.long, device=poses.device))
            torch.testing.assert_close(camera_poses, relative, atol=1e-7, rtol=1e-7)
            reference = poses.cpu().numpy().astype(np.float64)
            reference = np.linalg.inv(reference[0]) @ reference
            np.testing.assert_allclose(camera_poses[0].cpu().numpy(), reference, atol=1e-6, rtol=1e-6)
            torch.testing.assert_close(intrinsics[0], torch.from_numpy(traj["intrinsics"][window["poses"]]).to(intrinsics.device))
            indices = window["target"]
            rgb = np.array(self.guidance_rgb[indices], dtype=np.float32)
            alpha = np.array(self.guidance_alpha[indices], dtype=np.float32)
            assert np.isfinite(rgb).all() and np.isfinite(alpha).all()
            row = dict(chunk=self.current_chunk, context_frames=context,
                       raw_target_frames=[indices[0],indices[-1]], raw_frame_count=len(indices),
                       extra_prefix_discarded=window["extra_prefix"],
                       exported_target_frames=[self.current_chunk*80,self.current_chunk*80+80],
                       actual_context_global_frames=indices[:context],
                       valid_fraction=float((alpha >= .5).mean()),
                       caption_sha256=hashlib.sha256(captions[self.current_chunk].encode()).hexdigest())
            self.calls.append(row)
            (Path(self.pm.exp_dir) / "geometry_bridge_calls.json").write_text(json.dumps(self.calls, indent=2))
            print("CONTEXT GEOMETRY BRIDGE:", json.dumps(row), flush=True)
            return (torch.from_numpy(rgb).permute(0,3,1,2).unsqueeze(0).to(video_tensor.device),
                    torch.from_numpy(alpha).unsqueeze(0).unsqueeze(2).to(video_tensor.device), None)

        def run_inference_chunk(self, chunk_idx, input_video_path, chunk_poses,
                                chunk_intrinsics, context_frames, is_first_chunk, **kwargs):
            self.current_chunk = chunk_idx
            self.window = context_window(chunk_idx, args.context_frames)
            ids = self.window["poses"]
            cp = torch.from_numpy(traj["c2w"][ids]).unsqueeze(0).to(self.device)
            ck = torch.from_numpy(traj["intrinsics"][ids]).unsqueeze(0).to(self.device)
            original_preprocess, original_save = pc.preprocess_video_from_path, pc.imageio.mimsave
            extra = self.window["extra_prefix"]

            def prepare(*a, **kw):
                video = original_preprocess(*a, **kw)
                assert video.shape[0] == 81
                if extra:
                    video = torch.cat([video[:1].expand(extra, -1, -1, -1), video], dim=0)
                return video

            def save(path, frames, *a, **kw):
                assert len(frames) == 81+extra
                if extra:
                    raw = Path(self.pm.exp_dir) / "raw_context_chunks"
                    raw.mkdir(exist_ok=True)
                    original_save(str(raw / f"chunk_{chunk_idx:03d}_{len(frames)}frames.mp4"), frames, *a, **kw)
                # Trim before encoding so the delivered chunk incurs the same
                # single chunk encode and final stitch encode as the baseline.
                return original_save(path, frames[extra:], *a, **kw)

            pc.preprocess_video_from_path, pc.imageio.mimsave = prepare, save
            try:
                return super().run_inference_chunk(chunk_idx, input_video_path, cp, ck,
                                                    self.window["context"], is_first_chunk, **kwargs)
            finally:
                pc.preprocess_video_from_path, pc.imageio.mimsave = original_preprocess, original_save

    pc.WanVideoGenerator = ContextGenerator
    sys.argv = [sys.argv[0]] + remainder
    try:
        runner.main()
        generator = instances[0]
        assert len(generator.calls) == 4
        output = Path(generator.cfg.experiment.output_root).parent
        report = json.loads((output / "report.json").read_text())
        report.update(context_frames_2nd=args.context_frames,
                      raw_chunk_frames=[x["raw_frame_count"] for x in generator.calls],
                      context_note="Real overlap is 5 frames (or configured 1+4k); excess overlap is trimmed before chunk encoding; 321-frame requested camera grid is unchanged.")
        (output / "report.json").write_text(json.dumps(report, indent=2))
        from PIL import Image
        np.testing.assert_array_equal(np.array(Image.open(output / "input_prepared.png")),
                                      np.array(Image.open(baseline / "input_prepared.png")))
        for field in ("c2w", "intrinsics", "fps"):
            np.testing.assert_array_equal(np.load(output / "requested_camera_trajectory.npz")[field], traj[field])
        (output / "pipeline_report.json").write_text(json.dumps(dict(
            pipeline=["MapAnything depth", "GaME static scene rendering", "WorldWarp diffusion"],
            guidance_dir=str(guidance), baseline=str(baseline), calls=generator.calls,
            original_input_pixels_equal=True, original_camera_trajectory_equal=True,
            baseline_captions_reused=not (baseline/'reference.json').exists(),
            prepared_reference_used=(baseline/'reference.json').exists(), worldwarp_internal_ttt3r_warper_used=False,
            geometry_updates_from_generated_frames=False, context_frames_2nd=args.context_frames,
            noise_note="Same initial seed; longer context windows change latent tensor shapes and thus noise placement after the first chunk."), indent=2))
    finally:
        pc.WanVideoGenerator, pc.batch_warp_frames_via_3dgs = original_class, original_warper


if __name__ == "__main__":
    main()
