"""Geometry adapters using MapAnything output and WorldWarp's native GS code."""
import json
import time
from pathlib import Path

import numpy as np


def select_history(chunk_idx, anchor):
    """Five evenly spaced real frames; never include padded context frames."""
    if chunk_idx == 0:
        return [(0, True, None)]
    start = (chunk_idx - 1) * 80
    result = [(start + local, False, local) for local in (0, 20, 40, 60, 80)]
    if anchor:
        result = [(0, True, None)] + [r for r in result if r[0] != 0]
    return result


def rotation_source_support(source_poses, source_ks, source_valid, target_pose, target_k):
    """Exact observed FOV for rotation about a shared camera center."""
    import cv2
    if not np.allclose(source_poses[:, :3, 3], target_pose[:3, 3], atol=1e-8):
        raise ValueError('Rotation visibility requires a fixed camera center')
    h, w = source_valid.shape[1:]
    support = np.zeros((h, w), np.float32)
    for pose, k, mask in zip(source_poses, source_ks, source_valid):
        homography = (target_k.astype(np.float64) @ target_pose[:3, :3].astype(np.float64).T
                      @ pose[:3, :3].astype(np.float64) @ np.linalg.inv(k.astype(np.float64)))
        coverage = cv2.warpPerspective(mask.astype(np.float32), homography, (w, h), flags=cv2.INTER_LINEAR)
        support = np.maximum(support, coverage)
    return (support > .999).astype(np.float32)


def unproject_sources(rgbd, device):
    import torch
    rgb, depths = rgbd['rgb'], rgbd['depth_z']
    n, h, w, _ = rgb.shape
    yy, xx = np.mgrid[:h, :w].astype(np.float64)
    pixels = np.stack([xx, yy, np.ones_like(xx)], -1)
    sources = []
    for i in range(n):
        valid = rgbd['valid'][i] & np.isfinite(depths[i]) & (depths[i] > 0)
        k, pose = rgbd['intrinsics'][i].astype(np.float64), rgbd['c2w'][i].astype(np.float64)
        camera = (pixels @ np.linalg.inv(k).T) * depths[i, ..., None]
        world = camera @ pose[:3, :3].T + pose[:3, 3]
        sources.append((torch.tensor(world[valid], dtype=torch.float32, device=device),
                        torch.tensor(rgb[i][valid] / 255., dtype=torch.float32, device=device)))
    return sources


def splat_points(points, colors, target_pose, target_k, height, width):
    """Bilinear forward splat with a per-view z-buffer; no learned renderer."""
    import torch
    camera = (points - target_pose[:3, 3]) @ target_pose[:3, :3]
    positive = torch.isfinite(camera).all(-1) & (camera[:, 2] > 1e-4)
    camera, colors = camera[positive], colors[positive]
    projected = camera @ target_k.T
    uv = projected[:, :2] / projected[:, 2:3]
    base = torch.floor(uv).long()
    fraction = uv - base
    ids, weights, depths, color_values = [], [], [], []
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        xy = base + torch.tensor([dx, dy], device=points.device)
        weight = (fraction[:, 0] if dx else 1-fraction[:, 0]) * (fraction[:, 1] if dy else 1-fraction[:, 1])
        inside = (xy[:, 0] >= 0) & (xy[:, 0] < width) & (xy[:, 1] >= 0) & (xy[:, 1] < height) & (weight > 1e-6)
        ids.append(xy[inside, 1] * width + xy[inside, 0])
        weights.append(weight[inside])
        depths.append(camera[inside, 2])
        color_values.append(colors[inside])
    ids, weights, depths, color_values = map(torch.cat, (ids, weights, depths, color_values))
    nearest = torch.full((height*width,), float('inf'), device=points.device)
    nearest.scatter_reduce_(0, ids, depths, reduce='amin', include_self=True)
    visible = depths <= nearest[ids] * 1.02 + 1e-6
    ids, weights, color_values = ids[visible], weights[visible], color_values[visible]
    denominator = torch.zeros(height*width, device=points.device)
    numerator = torch.zeros((height*width, 3), device=points.device)
    denominator.scatter_add_(0, ids, weights)
    numerator.scatter_add_(0, ids[:, None].expand(-1, 3), color_values * weights[:, None])
    rendered = (numerator / denominator.clamp_min(1e-8)[:, None]).reshape(height, width, 3)
    return rendered, denominator.reshape(height, width).clamp(0, 1)


def render_geometry(rgbd_path, target_poses, target_ks, backend, output_dir, iterations=500,
                    anchor_weight=2, device='cuda'):
    import torch
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = np.load(rgbd_path)
    n, h, w, _ = data['rgb'].shape
    target_poses = np.asarray(target_poses, dtype=np.float32)
    target_ks = np.asarray(target_ks, dtype=np.float32)
    started = time.monotonic()
    weights = np.where(data['observed'], anchor_weight, 1).astype(np.int64)
    # A one-view first chunk should not differ only because of duplicate IDs.
    if n == 1:
        weights[:] = 1
    rgb_out, alpha_out = [], []
    report = dict(backend=backend, source_frame_ids=data['frame_ids'].tolist(),
                  observed=data['observed'].tolist(), source_weights=weights.tolist(),
                  target_count=len(target_poses), gaussians=None)
    pure_rotation = np.allclose(data['c2w'][:, :3, 3], target_poses[0, :3, 3], atol=1e-8) and np.allclose(target_poses[:, :3, 3], target_poses[0, :3, 3], atol=1e-8)
    report['visibility'] = 'Exact rotation-projected source validity and rendered coverage' if pure_rotation else 'Depth consistency and rendered coverage'
    torch.manual_seed(32)
    torch.cuda.manual_seed_all(32)
    np.random.seed(32)
    if backend == 'gs':
        from src.ttt3r.ttt3r import GS3DWarper
        warper = GS3DWarper(None, device=device, num_gs_iterations=iterations, optimize_poses=False)
        video = torch.from_numpy(data['rgb'].copy()).permute(0, 3, 1, 2).float()[None] / 255.
        depths = torch.from_numpy(data['depth_z'].copy()).float()
        source_poses = torch.from_numpy(data['c2w'].copy()).float()
        source_ks = torch.from_numpy(data['intrinsics'].copy()).float()
        src_ids = torch.arange(n)[None]
        splats = torch.nn.ParameterDict(warper._initialize_splats_from_depth(
            video, depths, source_poses, source_ks, src_ids, conf_threshold=1e-4,
            max_points_per_frame=50000, max_points=350000))
        train_ids = torch.from_numpy(np.repeat(np.arange(n), weights))[None]
        splats, _ = warper._train_splats(splats, warper._create_optimizers(splats),
            video, depths, source_poses, source_ks, train_ids, num_iterations=iterations,
            optimize_poses=False)
        for name, parameter in splats.items():
            if not torch.isfinite(parameter).all():
                raise RuntimeError(f'Nonfinite native 3DGS parameter: {name}')
        torch.save(dict(splats={k:v.detach().cpu() for k,v in splats.items()},
            source_poses=source_poses, source_intrinsics=source_ks,
            source_frame_ids=data['frame_ids'], iterations=iterations), output_dir/'native_3dgs.pt')
        report['gaussians'] = len(splats['means'])
        report['iterations'] = iterations
        source_poses, source_ks, depths = (x.to(device) for x in (source_poses, source_ks, depths))
        with torch.no_grad():
            for pose, k in zip(target_poses, target_ks):
                pose_t = torch.from_numpy(pose).to(device)[None]
                k_t = torch.from_numpy(k).to(device)[None]
                color, alpha, _ = warper._rasterize_splats(splats, pose_t, k_t, w, h)
                if pure_rotation:
                    support = rotation_source_support(data['c2w'], data['intrinsics'], data['valid'], pose, k)
                    valid = torch.from_numpy(support).to(device)[None, ..., None]
                else:
                    valid = warper._compute_geometric_validity_mask(splats, pose_t, k_t,
                        source_poses, source_ks, depths, w, h, depth_threshold=.1, min_sources=1)
                rgb_out.append(color[0].clamp(0, 1).cpu().numpy())
                alpha_out.append((alpha*valid)[0, ..., 0].cpu().numpy())
        del splats, warper
    elif backend == 'points':
        sources = unproject_sources(data, device)
        with torch.no_grad():
            for pose, k in zip(target_poses, target_ks):
                numerator = torch.zeros((h, w, 3), device=device)
                denominator = torch.zeros((h, w), device=device)
                support = torch.zeros((h, w), device=device)
                for (points, colors), weight in zip(sources, weights):
                    color, coverage = splat_points(points, colors, torch.from_numpy(pose).to(device),
                        torch.from_numpy(k).to(device), h, w)
                    numerator += color * coverage[..., None] * int(weight)
                    denominator += coverage * int(weight)
                    support = torch.maximum(support, coverage)
                rgb_out.append((numerator / denominator.clamp_min(1e-8)[..., None]).clamp(0, 1).cpu().numpy())
                coverage = support.cpu().numpy()
                if pure_rotation:
                    coverage *= rotation_source_support(data['c2w'], data['intrinsics'], data['valid'], pose, k)
                alpha_out.append(coverage)
        report['points_per_source'] = [len(x[0]) for x in sources]
        report['fusion'] = 'Per-view z-buffer, bilinear splatting, weighted color fusion; observed input weight 2.'
        del sources
    else:
        raise ValueError(backend)
    rgb, alpha = np.stack(rgb_out), np.stack(alpha_out)
    if not np.isfinite(rgb).all() or not np.isfinite(alpha).all():
        raise RuntimeError('Nonfinite geometry rendering')
    np.save(output_dir/'warped_rgb.npy', rgb.astype(np.float16))
    np.save(output_dir/'valid_alpha.npy', alpha.astype(np.float16))
    np.savez_compressed(output_dir/'target_cameras.npz', c2w=target_poses, intrinsics=target_ks)
    report.update(elapsed_seconds=time.monotonic()-started,
        valid_fraction_per_frame=(alpha >= .5).mean(axis=(1, 2)).tolist(),
        game_used=False, ttt3r_inference_used=False)
    (output_dir/'render_report.json').write_text(json.dumps(report, indent=2))
    torch.cuda.empty_cache()
    return rgb, alpha, report
