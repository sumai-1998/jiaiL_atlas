#!/usr/bin/env python3
"""Run MapAnything in its own environment for a WorldWarp history window."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    import cv2
    import numpy as np
    import torch
    from mapanything.models import MapAnything
    from mapanything.utils.image import preprocess_inputs

    cv2.setNumThreads(4)
    torch.set_num_threads(4)
    torch.manual_seed(32)
    torch.cuda.manual_seed_all(32)
    root = Path(__file__).resolve().parents[1]
    data = np.load(args.input)
    rgb, ks, poses = data['rgb'], data['intrinsics'], data['c2w']
    n, h, w, _ = rgb.shape
    assert ks.shape == (n, 3, 3) and poses.shape == (n, 4, 4)
    # These are requested virtual cameras. Pure rotation supplies no metric
    # baseline, so do not encode the zero translation as a measured scale.
    inputs = [dict(img=rgb[i], intrinsics=ks[i], camera_poses=poses[i],
                   is_metric_scale=False) for i in range(n)]
    width = round(w / h * 518 / 14) * 14
    views = preprocess_inputs(inputs, resize_mode='fixed_size', size=(width, 518), verbose=True)
    processed_ks = [v['intrinsics'][0].numpy().copy() for v in views]
    started = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    model = MapAnything.from_pretrained(str(root/'checkpoints/mapanything')).eval().cuda()
    with torch.inference_mode():
        predictions = model.infer(views, memory_efficient_inference=True, minibatch_size=1,
            use_amp=True, amp_dtype='bf16', apply_mask=True, mask_edges=False,
            apply_confidence_mask=False, ignore_pose_scale_inputs=True)
    if os.environ.get('CLASSROOM_CAPTURE_MAP_NATIVE') == '1':
        from classroom_geometry_trace import save_map_native
        save_map_native(args.output, predictions, views, data['frame_ids'])
    y, x = np.mgrid[:h, :w].astype(np.float32)
    pixels = np.stack([x, y, np.ones_like(x)], -1)
    depths, masks, confs, diagnostics = [], [], [], []
    for i, pred in enumerate(predictions):
        to_np = lambda t: t.detach().float().cpu().numpy()[0]
        depth = to_np(pred['depth_z'])[..., 0]
        valid = (to_np(pred['mask'])[..., 0] > 0) & np.isfinite(depth) & (depth > 0)
        conf = to_np(pred['conf']).squeeze()
        mapped = pixels @ (processed_ks[i].astype(np.float64) @ np.linalg.inv(ks[i].astype(np.float64))).T
        mx, my = ((mapped[..., j] / mapped[..., 2]).astype(np.float32) for j in (0, 1))
        weight = cv2.remap(valid.astype(np.float32), mx, my, cv2.INTER_LINEAR)
        numerator = cv2.remap(np.where(valid, depth, 0).astype(np.float32), mx, my, cv2.INTER_LINEAR)
        restored = numerator / np.maximum(weight, 1e-6)
        mask = (weight > .999) & np.isfinite(restored) & (restored > 0)
        restored[~mask] = 0
        if mask.mean() < .5:
            raise RuntimeError(f'Insufficient valid MapAnything geometry for source {i}: {mask.mean()}')
        depths.append(restored)
        masks.append(mask)
        confs.append(cv2.remap(conf, mx, my, cv2.INTER_LINEAR))
        diagnostics.append(dict(valid_fraction=float(mask.mean()),
            depth_percentiles=np.percentile(restored[mask], [5, 50, 95]).tolist(),
            processed_K=processed_ks[i].tolist(), predicted_K=to_np(pred['intrinsics']).tolist(),
            predicted_c2w=to_np(pred['camera_poses']).tolist()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, rgb=rgb, depth_z=np.stack(depths), valid=np.stack(masks),
        confidence=np.stack(confs), intrinsics=ks, c2w=poses, frame_ids=data['frame_ids'],
        observed=data['observed'])
    report = dict(status='complete', model=str(root/'checkpoints/mapanything'),
        input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
        views=n, frame_ids=data['frame_ids'].tolist(), observed=data['observed'].tolist(),
        processed_size=[width, 518], output_size=[w, h], diagnostics=diagnostics,
        camera_policy='Condition on requested K/c2w; retain supplied cameras downstream.',
        metric_scale='Predicted only; pure rotation has no measured metric baseline.',
        mask_edges=False, confidence_filter=False, elapsed_seconds=time.monotonic()-started,
        peak_gpu_memory_gib=torch.cuda.max_memory_allocated()/2**30)
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
