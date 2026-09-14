#!/usr/bin/env python3
"""Decode a generated video, inspect chunk joins, and save frame previews."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video")
    parser.add_argument("--expected-frames", type=int, default=321)
    parser.add_argument("--motion-type", choices=["truck-left", "pan-left"], default="truck-left")
    args = parser.parse_args()
    video = Path(args.video).resolve()
    output = video.parent / "inspection"
    output.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    previews = set([0, 40, 79, 80, 81, 120, 159, 160, 161, 200, 239, 240, 241, 280, 320])
    frames, motion, differences = {}, [], []
    previous = None
    count = 0
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        if count in previews:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            frames[count] = Image.fromarray(rgb)
            frames[count].save(output / f"frame_{count:03d}.jpg", quality=95)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        if previous is not None:
            differences.append(float(np.abs(gray.astype(float) - previous.astype(float)).mean()))
            points = cv2.goodFeaturesToTrack(previous, maxCorners=300, qualityLevel=0.02,
                                            minDistance=10, blockSize=7)
            if points is not None:
                nxt, status, _ = cv2.calcOpticalFlowPyrLK(previous, gray, points, None)
                back, back_status, _ = cv2.calcOpticalFlowPyrLK(gray, previous, nxt, None)
                good = (status[:, 0] == 1) & (back_status[:, 0] == 1)
                good &= np.linalg.norm(points[:, 0] - back[:, 0], axis=1) < 1.0
                delta = nxt[good, 0] - points[good, 0]
                if len(delta) >= 10:
                    motion.append(dict(frame=count, tracked_points=len(delta),
                                       median_dx_px=float(np.median(delta[:, 0])),
                                       median_dy_px=float(np.median(delta[:, 1]))))
        previous = gray
        count += 1
    cap.release()
    if count != args.expected_frames:
        raise RuntimeError(f"Expected {args.expected_frames} frames, decoded {count}")
    thumb_width = 192
    thumb_height = round(height * thumb_width / width)
    contact = Image.new("RGB", (5 * thumb_width, 3 * (thumb_height + 28)), "#202020")
    draw = ImageDraw.Draw(contact)
    for pos, (idx, frame) in enumerate(sorted(frames.items())):
        x, y = (pos % 5) * thumb_width, (pos // 5) * (thumb_height + 28)
        contact.paste(frame.resize((thumb_width, thumb_height)), (x, y))
        draw.text((x + 5, y + thumb_height + 7), f"frame {idx:03d} | {idx/fps:.2f}s", fill="white")
    contact.save(output / "contact_sheet.jpg", quality=95)
    chunks = []
    for idx in range(4):
        local = [m for m in motion if idx*80 < m["frame"] <= (idx+1)*80]
        chunks.append(dict(chunk=idx+1, median_dx_px_per_frame=float(np.median([m["median_dx_px"] for m in local])),
                           median_dy_px_per_frame=float(np.median([m["median_dy_px"] for m in local]))))
    report = dict(video=str(video), decoded_frames=count, fps=fps, width=width, height=height,
                  duration_seconds=count/fps,
                  joins=[dict(frame=i, previous_pair_mae=differences[i-1], next_pair_mae=differences[i]) for i in (80,160,240)],
                  median_frame_pair_mae=float(np.median(differences)),
                  observed_image_motion_per_chunk=chunks,
                  requested_motion=args.motion_type,
                  motion_note="Image feature motion is a diagnostic, not calibrated 3D camera speed or angular velocity. Positive image X motion is expected when a camera translates or turns left in a stationary scene.",
                  feature_motion=motion)
    (output / "validation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k != "feature_motion"}, indent=2))


if __name__ == "__main__":
    main()
