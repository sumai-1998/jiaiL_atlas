#!/usr/bin/env python3
"""Estimate depth with MapAnything while retaining the baseline virtual camera."""
import argparse
import json
import time
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--image", required=True)
    p.add_argument("--trajectory", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    import cv2
    import numpy as np
    import torch
    from PIL import Image
    from mapanything.models import MapAnything
    from mapanything.utils.image import preprocess_inputs

    root = Path(__file__).resolve().parents[1]
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rgb = np.array(Image.open(a.image).convert("RGB"))
    h, w = rgb.shape[:2]
    trajectory = np.load(a.trajectory)
    K = trajectory["intrinsics"][0].astype(np.float32)
    pose = trajectory["c2w"][0].astype(np.float32)
    target_width = round((w / h) * 518 / 14) * 14
    views = preprocess_inputs([dict(img=rgb, intrinsics=K, camera_poses=pose)],
                              resize_mode="fixed_size", size=(target_width, 518), verbose=True)
    processed_K = views[0]["intrinsics"][0].numpy().copy()
    start = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    model = MapAnything.from_pretrained(str(root / "checkpoints/mapanything")).eval().cuda()
    with torch.inference_mode():
        pred = model.infer(views, memory_efficient_inference=True, minibatch_size=1,
                           use_amp=True, amp_dtype="bf16", apply_mask=True,
                           mask_edges=False, apply_confidence_mask=False)[0]
    to_np = lambda t: t.detach().float().cpu().numpy()[0]
    depth = to_np(pred["depth_z"])[..., 0]
    valid = to_np(pred["mask"])[..., 0] > 0
    confidence = to_np(pred["conf"]).squeeze()
    # Undo the preprocessing crop/resize using the camera transform, rather than
    # resizing the depth blindly and shifting the principal point.
    y, x = np.mgrid[:h, :w].astype(np.float32)
    pixels = np.stack([x, y, np.ones_like(x)], -1)
    processed_pixels = pixels @ (processed_K @ np.linalg.inv(K)).T
    mx = (processed_pixels[..., 0] / processed_pixels[..., 2]).astype(np.float32)
    my = (processed_pixels[..., 1] / processed_pixels[..., 2]).astype(np.float32)
    depth_full = cv2.remap(np.nan_to_num(depth, nan=0), mx, my, cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT)
    valid_weight = cv2.remap(valid.astype(np.float32), mx, my, cv2.INTER_LINEAR)
    depth_full /= np.maximum(valid_weight, 1e-6)
    valid_full = cv2.remap(valid.astype(np.uint8), mx, my, cv2.INTER_NEAREST).astype(bool)
    confidence_full = cv2.remap(confidence, mx, my, cv2.INTER_LINEAR)
    valid_full &= np.isfinite(depth_full) & (depth_full > 0)
    depth_full[~valid_full] = 0
    if valid_full.mean() < 0.5:
        raise RuntimeError("Insufficient valid MapAnything depth")
    rays = pixels @ np.linalg.inv(K).T
    camera_points = rays * depth_full[..., None]
    world_points = camera_points @ pose[:3, :3].T + pose[:3, 3]
    np.savez_compressed(out / "posed_rgbd.npz", rgb=rgb[None], depth_z=depth_full[None],
                        valid=valid_full[None], intrinsics=K[None], c2w=pose[None],
                        confidence=confidence_full[None])
    np.savez_compressed(out / "pointmaps.npz", points=world_points[None], valid=valid_full[None])
    raw = dict(depth_z=depth, valid=valid, intrinsics=to_np(pred["intrinsics"]),
               c2w=to_np(pred["camera_poses"]))
    np.savez_compressed(out / "raw_prediction.npz", **raw)
    report = dict(project="MapAnything", input_image=str(Path(a.image).resolve()),
                  calibration_source=str(Path(a.trajectory).resolve()),
                  model=str(root / "checkpoints/mapanything"), source_kind="observed",
                  output_size=[w, h], processed_size=[depth.shape[1], depth.shape[0]],
                  processed_K=processed_K.tolist(), supplied_K=K.tolist(),
                  predicted_K_max_difference=float(np.abs(raw["intrinsics"]-processed_K).max()),
                  predicted_pose_max_difference=float(np.abs(raw["c2w"]-pose).max()),
                  valid_fraction=float(valid_full.mean()),
                  depth_percentiles=np.percentile(depth_full[valid_full], [5,50,95]).tolist(),
                  elapsed_seconds=time.monotonic()-start,
                  peak_gpu_memory_gib=torch.cuda.max_memory_allocated()/2**30,
                  mask_edges=False,
                  note="Single-view predicted depth; camera calibration/pose held to baseline. Keep depth-edge pixels for dense source-image fitting; non-ambiguous mask retained.")
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
