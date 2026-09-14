#!/usr/bin/env python3
"""Use MapAnything -> GaME RGB/alpha renders inside WorldWarp's diffusion path."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "WorldWarp"))


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--guidance-dir", required=True)
    parser.add_argument("--baseline", required=True)
    args, remainder = parser.parse_known_args()
    guidance = Path(args.guidance_dir).resolve()
    baseline = Path(args.baseline).resolve()
    import numpy as np
    import torch
    import pose_control as pc
    import generate_worldwarp_rotation as runner
    from chunk_trajectory import chunk_pose_bounds

    baseline_report = json.loads((baseline / "report.json").read_text())
    baseline_trajectory = np.load(baseline / "requested_camera_trajectory.npz")
    guidance_trajectory = np.load(guidance / "trajectory.npz")
    np.testing.assert_array_equal(baseline_trajectory["c2w"], guidance_trajectory["c2w"])
    np.testing.assert_array_equal(baseline_trajectory["intrinsics"], guidance_trajectory["intrinsics"])
    baseline_artifacts = Path(baseline_report["completed_chunks"][0]["path"]).parent.parent
    captions = [(baseline_artifacts / "captions" / f"chunk_{idx:03d}.txt").read_text()
                for idx in range(baseline_report["chunks"])]
    instances = []
    original_generator = pc.WanVideoGenerator
    original_warper = pc.batch_warp_frames_via_3dgs

    class GuidedGenerator(original_generator):
        def __init__(self, cfg):
            super().__init__(cfg)
            self.guidance_index = 0
            self.guidance_calls = []
            self.guidance_rgb = np.load(guidance / "warped_rgb.npy", mmap_mode="r")
            self.guidance_alpha = np.load(guidance / "valid_alpha.npy", mmap_mode="r")
            expected = (321, cfg.inference_params.height, cfg.inference_params.width)
            if self.guidance_rgb.shape != (*expected, 3) or self.guidance_alpha.shape != expected:
                raise ValueError("Unexpected geometry guidance shape")
            # The original WorldWarp method still performs VAE encoding, mask erosion,
            # asynchronous diffusion sampling and decoding. Only its geometric warper
            # is replaced with actual GaME checkpoint renders in this process.
            pc.batch_warp_frames_via_3dgs = self.geometry_warp
            instances.append(self)

        def _init_captioner(self, is_vl=True):
            self.caption_model = "cached_baseline_captions"

        def get_caption(self, video_path=None, prompt_text=None, style_ref=None):
            return captions[self.guidance_index]

        def geometry_warp(self, source_ids, target_ids, video_tensor, camera_poses,
                          intrinsics, ttt3r, **kwargs):
            idx = self.guidance_index
            n, context = video_tensor.shape[1], self.cfg.inference_params.context_frames_2nd
            if n != 81 or context != 1:
                raise ValueError("This controlled experiment expects 81-frame chunks with one overlap frame")
            start, end = chunk_pose_bounds(idx, n, context)
            window = torch.from_numpy(guidance_trajectory["c2w"][start:end]).to(camera_poses.device)
            # Match WorldWarp's batched rigid inverse. A separate unbatched CUDA
            # inverse/matmul can take the TF32 path and truncate rotation values.
            relative = pc.get_relative_poses(window.unsqueeze(0), torch.zeros(
                (1, 1), dtype=torch.long, device=camera_poses.device))[0]
            torch.testing.assert_close(camera_poses[0], relative, atol=1e-7, rtol=1e-7)
            reference = guidance_trajectory["c2w"][start:end].astype(np.float64)
            reference = np.linalg.inv(reference[0]) @ reference
            np.testing.assert_allclose(camera_poses[0].cpu().numpy(), reference,
                                       atol=1e-6, rtol=1e-6)
            torch.testing.assert_close(intrinsics[0], torch.from_numpy(guidance_trajectory["intrinsics"][start:end]).to(intrinsics.device))
            local_start = 0 if idx == 0 else n-context
            torch.testing.assert_close(target_ids[0], torch.arange(local_start,local_start+n,device=target_ids.device))
            global_start = idx*(n-context)
            rgb = np.array(self.guidance_rgb[global_start:global_start+n], dtype=np.float32)
            alpha = np.array(self.guidance_alpha[global_start:global_start+n], dtype=np.float32)
            assert np.isfinite(rgb).all() and np.isfinite(alpha).all()
            row = dict(chunk=idx, global_target_frames=[global_start,global_start+n-1],
                       rgb_shape=list(rgb.shape), valid_fraction=float((alpha >= 0.5).mean()),
                       mean_alpha=float(alpha.mean()), caption_sha256=hashlib.sha256(captions[idx].encode()).hexdigest())
            self.guidance_calls.append(row)
            (Path(self.pm.exp_dir) / "geometry_bridge_calls.json").write_text(json.dumps(self.guidance_calls,indent=2))
            print("MAPANYTHING -> GAME -> WORLDWARP:", json.dumps(row), flush=True)
            self.guidance_index += 1
            return (torch.from_numpy(rgb).permute(0,3,1,2).unsqueeze(0).to(video_tensor.device),
                    torch.from_numpy(alpha).unsqueeze(0).unsqueeze(2).to(video_tensor.device), None)

    pc.WanVideoGenerator = GuidedGenerator
    sys.argv = [sys.argv[0]] + remainder
    try:
        runner.main()
        generator = instances[0]
        assert generator.guidance_index == 4
        output = Path(generator.cfg.experiment.output_root).parent
        from PIL import Image
        np.testing.assert_array_equal(np.array(Image.open(output / "input_prepared.png")),
                                      np.array(Image.open(baseline / "input_prepared.png")))
        pipeline = dict(pipeline=["MapAnything calibrated single-view depth", "GaME static scene fitting and trajectory rendering", "WorldWarp geometry-conditioned diffusion"],
                        guidance_dir=str(guidance), baseline=str(baseline), calls=generator.guidance_calls,
                        original_input_pixels_equal=True, original_camera_trajectory_equal=True,
                        baseline_captions_reused=True, worldwarp_internal_ttt3r_warper_used=False,
                        geometry_updates_from_generated_frames=False,
                        note="This is an actual geometry-conditioning replacement experiment, not a postprocessing pass or a full persistent-world feedback loop.")
        (output / "pipeline_report.json").write_text(json.dumps(pipeline, indent=2))
    finally:
        pc.WanVideoGenerator = original_generator
        pc.batch_warp_frames_via_3dgs = original_warper


if __name__ == "__main__": main()
