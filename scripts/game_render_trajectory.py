#!/usr/bin/env python3
"""Render an actual GaME checkpoint to RGB/alpha conditioning for WorldWarp."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "GaME"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--rgbd", required=True)
    parser.add_argument("--trajectory", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--motion-mode", choices=["rotation", "se3"], default="rotation",
                        help="SE3 uses native GS visibility; rotation retains input-FOV clipping")
    args = parser.parse_args()
    import cv2
    import numpy as np
    import torch
    from PIL import Image
    from src.entities.game import GaME
    from src.flashsplat.gaussian_renderer import flashsplat_render
    from src.utils import utils
    from game_camera_adapter import install_and_check

    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    scene = Path(args.scene).resolve()
    package = np.load(args.rgbd)
    rgb = package["rgb"][0]
    depth = package["depth_z"][0].copy()
    depth[~package["valid"][0]] = 0
    source_K = package["intrinsics"][0]
    source_c2w = package["c2w"][0]
    h, w = depth.shape
    sample = dict(color=rgb, depth=depth, pose=np.linalg.inv(source_c2w).astype(np.float32),
                  intrinsics=source_K, masks=torch.ones((1,h,w), dtype=torch.bool))

    class Dataset:
        start_frame = 0
        run_id = "static_npz"
        def __len__(self): return 1
        def __getitem__(self, index):
            if index != 0: raise IndexError(index)
            return sample

    start = time.monotonic()
    projection_error = install_and_check()
    config = json.loads((scene / "configs.json").read_text())["slam"]
    model = GaME(config, wandb_online=False,
                 checkpoint_path=scene / "checkpoints/checkpoint.pth", all_train_data=[Dataset()])
    trajectory = np.load(args.trajectory)
    c2w, Ks = trajectory["c2w"], trajectory["intrinsics"]
    if args.motion_mode == 'rotation':
        assert np.allclose(c2w[:, :3, 3], source_c2w[:3, 3])
    count = len(c2w)
    colors = np.lib.format.open_memmap(out / "warped_rgb.npy", mode="w+", dtype=np.float16,
                                       shape=(count, h, w, 3))
    alphas = np.lib.format.open_memmap(out / "valid_alpha.npy", mode="w+", dtype=np.float16,
                                       shape=(count, h, w))
    dummy_color = torch.zeros(3, h, w, device="cuda")
    dummy_depth = torch.ones(h, w, device="cuda")
    background = torch.zeros(3, device="cuda")
    pipe = utils.flashsplat_pipe()
    reports = []
    capture_all = os.environ.get('CLASSROOM_CAPTURE_GAME_RENDER') == '1'
    if capture_all:
        (out/'frames').mkdir()
        (out/'rgb_frames').mkdir()
    for idx, (pose, K) in enumerate(zip(c2w, Ks)):
        camera = utils.flashsplat_cam(dummy_color, dummy_depth, None, K,
                                      torch.from_numpy(np.linalg.inv(pose).astype(np.float32)), idx)
        with torch.no_grad():
            prediction = flashsplat_render(camera, model.gaussian_model, pipe, background,
                                           obj_num=config["num_label_channels"])
        color = prediction["render"].clamp(0, 1).permute(1, 2, 0).detach().cpu().numpy()
        alpha = prediction["alpha"].clamp(0, 1).squeeze().detach().cpu().numpy()
        alpha_raw = alpha.copy() if capture_all else None
        # For this pure rotation, clip Gaussian tails to the observed input FOV.
        if args.motion_mode == 'rotation':
            H = K @ pose[:3, :3].T @ source_c2w[:3, :3] @ np.linalg.inv(source_K)
            support = cv2.warpPerspective(np.ones((h, w), np.uint8), H, (w, h), flags=cv2.INTER_NEAREST)
            alpha *= support
        if not np.isfinite(color).all() or not np.isfinite(alpha).all():
            raise RuntimeError(f"Non-finite GaME render at frame {idx}")
        colors[idx], alphas[idx] = color, alpha
        if capture_all:
            frame_values = dict(rgb=color, alpha_raw=alpha_raw, alpha_used=alpha,
                                c2w=pose, intrinsics=K)
            if 'depth' in prediction:
                frame_values['depth_z'] = prediction['depth'].detach().float().cpu().numpy()
            np.savez_compressed(out/'frames'/f'frame_{idx:03d}.npz', **frame_values)
            Image.fromarray(np.rint(color*255).astype(np.uint8)).save(out/'rgb_frames'/f'frame_{idx:03d}.png')
        if idx in (0, 49, 99, 149, 199, count-1, 80, 160, 240, 320):
            Image.fromarray(np.rint(color * 255).astype(np.uint8)).save(out / f"render_{idx:03d}.png")
            Image.fromarray(np.rint(alpha * 255).astype(np.uint8)).save(out / f"alpha_{idx:03d}.png")
        row = dict(frame=idx, mean_alpha=float(alpha.mean()), valid_fraction=float((alpha >= 0.5).mean()))
        if idx == 0:
            error = color - rgb / 255.
            row["source_psnr_db"] = float(-10 * np.log10(np.mean(error**2)))
            row["valid_source_psnr_db"] = float(-10 * np.log10(np.mean(error[alpha >= 0.5]**2)))
        reports.append(row)
        if idx % 40 == 0: print(json.dumps(row), flush=True)
    colors.flush()
    alphas.flush()
    np.savez_compressed(out / "trajectory.npz", c2w=c2w, intrinsics=Ks,
                        fps=trajectory["fps"] if 'fps' in trajectory else 30)
    report = dict(project="GaME", scene=str(scene), rgbd=str(Path(args.rgbd).resolve()),
                  trajectory=str(Path(args.trajectory).resolve()), frames=count, width=w, height=h,
                  gaussians=len(model.gaussian_model.get_xyz), projection_error_px=projection_error,
                  elapsed_seconds=time.monotonic()-start, renders=reports, motion_mode=args.motion_mode,
                  visibility='native GS alpha' if args.motion_mode=='se3' else 'GS alpha clipped to rotation input FOV',
                  note="One fixed GaME scene fitted to MapAnything RGB-D from the original image; RGB/alpha fed into WorldWarp diffusion. No generated frames were used to train this scene.")
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print("GaME trajectory guidance complete", flush=True)


if __name__ == "__main__": main()
