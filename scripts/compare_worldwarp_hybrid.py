#!/usr/bin/env python3
"""Compare two pure-rotation videos against the observed input field of view."""
import argparse
import csv
import json
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def rotation_homography(source_c2w, target_c2w, source_k, target_k):
    """Map source pixels to target pixels for rotation about a fixed center."""
    np.testing.assert_allclose(source_c2w[:3, 3], target_c2w[:3, 3], atol=1e-8)
    return (target_k.astype(np.float64) @ target_c2w[:3, :3].astype(np.float64).T
            @ source_c2w[:3, :3].astype(np.float64) @ np.linalg.inv(source_k))


def warp_and_mask(rgb, homography, size):
    warped = cv2.warpPerspective(rgb, homography, size, flags=cv2.INTER_LINEAR)
    coverage = cv2.warpPerspective(np.ones(rgb.shape[:2], np.float32), homography,
                                   size, flags=cv2.INTER_LINEAR)
    mask = cv2.erode((coverage > .999).astype(np.uint8), np.ones((15, 15), np.uint8),
                     borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    return warped, mask


def gray(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)


def ssim_map(a, b):
    """Luma SSIM, population moments, 11x11 Gaussian sigma=1.5, range=255."""
    a, b = a.astype(np.float64), b.astype(np.float64)
    smooth = lambda x: cv2.GaussianBlur(x, (11, 11), 1.5)
    ma, mb = smooth(a), smooth(b)
    va, vb, cov = smooth(a*a)-ma*ma, smooth(b*b)-mb*mb, smooth(a*b)-ma*mb
    c1, c2 = (0.01*255)**2, (0.03*255)**2
    return ((2*ma*mb+c1)*(2*cov+c2))/((ma*ma+mb*mb+c1)*(va+vb+c2))


def reference_scores(rgb, reference, mask):
    delta = rgb.astype(np.float32) - reference.astype(np.float32)
    mse = float(np.mean(delta[mask]**2))
    return dict(known_psnr_db=float(10*np.log10(255**2/max(mse, 1e-12))),
                known_rgb_mae_255=float(np.mean(np.abs(delta[mask]))),
                known_luma_ssim=float(np.mean(ssim_map(gray(rgb), gray(reference))[mask])))


def feature_motion(previous, current, homography):
    prev_gray, cur_gray = gray(previous).astype(np.uint8), gray(current).astype(np.uint8)
    points = cv2.goodFeaturesToTrack(prev_gray, maxCorners=400, qualityLevel=.02,
                                    minDistance=8, blockSize=7)
    if points is None:
        return dict(tracked_points=0)
    nxt, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, cur_gray, points, None)
    back, back_status, _ = cv2.calcOpticalFlowPyrLK(cur_gray, prev_gray, nxt, None)
    good = (status[:, 0] == 1) & (back_status[:, 0] == 1)
    good &= np.linalg.norm(points[:, 0] - back[:, 0], axis=1) < 1.0
    predicted = cv2.perspectiveTransform(points, homography)[:, 0]
    h, w = prev_gray.shape
    good &= ((predicted[:, 0] > 8) & (predicted[:, 0] < w-8)
             & (predicted[:, 1] > 8) & (predicted[:, 1] < h-8))
    if np.count_nonzero(good) < 10:
        return dict(tracked_points=int(good.sum()))
    delta = nxt[good, 0]-points[good, 0]
    return dict(tracked_points=int(good.sum()), median_dx_px=float(np.median(delta[:, 0])),
                median_dy_px=float(np.median(delta[:, 1])),
                median_flow_error_px=float(np.median(np.linalg.norm(nxt[good, 0]-predicted[good], axis=1))))


def aggregate(rows):
    keys = ["known_psnr_db", "known_rgb_mae_255", "known_luma_ssim",
            "motion_compensated_luma_mae_255", "median_flow_error_px", "median_dx_px", "median_dy_px"]
    result = {}
    for key in keys:
        values = [r[key] for r in rows if key in r]
        result[key] = dict(mean=float(np.mean(values)), median=float(np.median(values)),
                           p95=float(np.percentile(values, 95)), count=len(values))
    return result


def main():
    cv2.setNumThreads(4)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--hybrid", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-strength-change", action="store_true",
                        help="Explicitly compare a strength ablation instead of asserting equality")
    parser.add_argument("--baseline-label", default="WorldWarp only")
    parser.add_argument("--hybrid-label", default="MapAnything + GaME + WorldWarp")
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    dirs = dict(baseline=args.baseline.resolve(), hybrid=args.hybrid.resolve())
    reports = {key: json.loads((path / "report.json").read_text()) for key, path in dirs.items()}
    if any(r["status"] != "complete" for r in reports.values()):
        raise ValueError("Both videos must be complete")
    reference = np.array(Image.open(dirs["baseline"] / "input_prepared.png").convert("RGB"))
    np.testing.assert_array_equal(reference, np.array(Image.open(dirs["hybrid"] / "input_prepared.png")))
    a = np.load(dirs["baseline"] / "requested_camera_trajectory.npz")
    b = np.load(dirs["hybrid"] / "requested_camera_trajectory.npz")
    for key in ("c2w", "intrinsics", "fps"):
        np.testing.assert_array_equal(a[key], b[key])
    for key in ("seed", "prepared_size", "chunks", "fps"):
        assert reports["baseline"][key] == reports["hybrid"][key], key
    if not args.allow_strength_change:
        assert reports["baseline"]["strength"] == reports["hybrid"]["strength"]
    varied_parameters = {}
    for key, default in (("strength", None), ("context_frames_2nd", 1)):
        before, after = reports["baseline"].get(key, default), reports["hybrid"].get(key, default)
        if before != after:
            varied_parameters[key] = dict(baseline=before, hybrid=after)
    for idx in range(reports["baseline"]["chunks"]):
        captions = []
        for report in reports.values():
            artifact = Path(report["completed_chunks"][idx]["path"]).parent.parent
            captions.append((artifact / "captions" / f"chunk_{idx:03d}.txt").read_bytes())
        assert captions[0] == captions[1], f"Caption differs in chunk {idx}"
    poses, ks, fps = a["c2w"], a["intrinsics"], float(a["fps"])
    h, w = reference.shape[:2]
    readers = {key: cv2.VideoCapture(r["output_video"]) for key, r in reports.items()}
    for reader in readers.values():
        assert reader.isOpened() and reader.get(cv2.CAP_PROP_FPS) == fps
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
    labels = dict(baseline=args.baseline_label, hybrid=args.hybrid_label)
    rows, previous, previews = {key: [] for key in readers}, {}, {}
    selected = [0, 80, 160, 240, 320]
    side_by_side = args.output / "classroom_side_by_side_10.7s.mp4"
    with imageio.get_writer(side_by_side, fps=fps, codec="libx264", quality=9, macro_block_size=1) as writer:
        for idx in range(len(poses)):
            frames = {}
            for key, reader in readers.items():
                ok, bgr = reader.read()
                if not ok:
                    raise ValueError(f"{key}: early end at frame {idx}")
                frames[key] = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                assert frames[key].shape == reference.shape
            hom = rotation_homography(poses[0], poses[idx], ks[0], ks[idx])
            target, mask = warp_and_mask(reference, hom, (w, h))
            relative = rotation_homography(poses[idx-1], poses[idx], ks[idx-1], ks[idx]) if idx else None
            panel = Image.new("RGB", (2*w, h+48), "#191d25")
            draw = ImageDraw.Draw(panel)
            for col, (key, rgb) in enumerate(frames.items()):
                row = dict(frame=idx, time_seconds=idx/fps, known_fraction=float(mask.mean()),
                           **reference_scores(rgb, target, mask))
                if idx:
                    warped_prev, temporal_mask = warp_and_mask(previous[key], relative, (w, h))
                    residual = np.abs(gray(rgb) - gray(warped_prev))
                    row["motion_compensated_luma_mae_255"] = float(residual[temporal_mask].mean())
                    row.update(feature_motion(previous[key], rgb, relative))
                rows[key].append(row)
                panel.paste(Image.fromarray(rgb), (col*w, 48))
                draw.text((col*w+12, 5), labels[key], fill="white", font=font)
                angle = abs(reports["baseline"]["total_angle_deg"])*idx/(len(poses)-1)
                draw.text((col*w+12, 26), f"{idx/fps:5.2f}s  |  left turn {angle:5.2f} deg", fill="#a8b9cb", font=font)
            writer.append_data(np.asarray(panel))
            if idx in selected:
                previews[idx] = panel
                panel.save(args.output / f"comparison_frame_{idx:03d}.jpg", quality=96)
                Image.fromarray(target).save(args.output / f"reference_frame_{idx:03d}.png")
                Image.fromarray(mask.astype(np.uint8)*255).save(args.output / f"reference_mask_{idx:03d}.png")
            previous = frames
            if idx % 80 == 0:
                print(json.dumps({"frame":idx, **{key: rows[key][-1] for key in rows}}), flush=True)
    for reader in readers.values():
        assert not reader.read()[0], "Unexpected extra video frames"
        reader.release()
    thumbnail = Image.new("RGB", (480*len(selected), 328), "#191d25")
    for i, idx in enumerate(selected):
        thumbnail.paste(previews[idx].resize((480, 328), Image.Resampling.LANCZOS), (480*i, 0))
    thumbnail.save(args.output / "comparison_contact_sheet.jpg", quality=96)
    summary = dict(baseline=str(dirs["baseline"]), hybrid=str(dirs["hybrid"]),
                   side_by_side=str(side_by_side), frames=len(poses), fps=fps,
                   labels=labels, varied_parameters=varied_parameters,
                   controlled_parameters=["input pixels", "camera poses and intrinsics", "seed", "frame count", "resolution", "per-chunk captions"] + ([] if "strength" in varied_parameters else ["strength"]),
                   method=dict(known_region="Original RGB warped by K_target R_target.T R_source inv(K_source); erosion by a 15x15 kernel on valid source FOV; no hidden-region ground truth.",
                               known_psnr="RGB PSNR with data range 255; aggregate is mean per-frame PSNR, excluding conditioning frame 0.",
                               known_ssim="Luma SSIM with 11x11 Gaussian sigma 1.5, population covariance, range 255, same eroded FOV mask.",
                               temporal="Luma MAE after warping previous frame with requested relative camera rotation, over eroded overlap; smaller can also reflect blur.",
                               flow="Median forward/backward-consistent KLT track error versus requested rotational homography; diagnostic, not recovered 3D camera pose.",
                               interpretation="One image and one random seed, static scene conditioning; no generated-frame feedback into GaME. No claim of general superiority."),
                   metrics={key: aggregate(value[1:]) for key, value in rows.items()},
                   chunks={key: [dict(chunk=i+1, **aggregate([r for r in value if i*80 < r["frame"] <= (i+1)*80])) for i in range(4)] for key, value in rows.items()},
                   joins={key: [value[i] for i in (81,161,241)] for key,value in rows.items()})
    (args.output / "comparison.json").write_text(json.dumps(summary, indent=2))
    (args.output / "per_frame.json").write_text(json.dumps(rows, indent=2))
    columns = ["method"] + list(dict.fromkeys(k for value in rows.values() for row in value for k in row))
    with (args.output / "per_frame.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for key, values in rows.items():
            writer.writerows(dict(method=key, **row) for row in values)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for key, values in rows.items():
        t = [r["time_seconds"] for r in values[1:]]
        for ax, field, label in zip(axes, ["known_psnr_db", "known_luma_ssim", "motion_compensated_luma_mae_255"],
                                    ["Observed-region RGB PSNR (dB)", "Observed-region luma SSIM", "Motion-compensated luma MAE"]):
            ax.plot(t, [r[field] for r in values[1:]], label=labels[key], linewidth=1.3)
            ax.set_ylabel(label)
    for ax in axes:
        for idx in (80,160,240):
            ax.axvline(idx/fps, color="gray", linestyle="--", alpha=.35)
        ax.grid(alpha=.2)
    axes[0].legend()
    axes[-1].set_xlabel("Time (s); dashed lines mark chunk boundaries")
    fig.tight_layout()
    fig.savefig(args.output / "metric_curves.png", dpi=160)
    plt.close(fig)
    print(json.dumps(summary["metrics"], indent=2))


if __name__ == "__main__":
    main()
