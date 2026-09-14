#!/usr/bin/env python3
"""Generate a WorldWarp video with a stationary camera rotating uniformly left."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "WorldWarp"))


def constant_y_rotation(total_frames, total_angle_deg):
    """OpenCV c2w rotation about camera Y; negative angles turn the camera left."""
    import numpy as np

    if total_frames < 2:
        raise ValueError("At least two frames are required")
    angles = np.deg2rad(np.linspace(0, total_angle_deg, total_frames, dtype=np.float64))
    poses = np.tile(np.eye(4, dtype=np.float64), (total_frames, 1, 1))
    poses[:, 0, 0] = np.cos(angles)
    poses[:, 0, 2] = np.sin(angles)
    poses[:, 2, 0] = -np.sin(angles)
    poses[:, 2, 2] = np.cos(angles)
    return poses.astype(np.float32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--chunks", type=int, default=4)
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=608)
    parser.add_argument("--total-angle-deg", type=float, default=-20.0,
                        help="Total camera rotation about Y in degrees; negative turns left")
    parser.add_argument("--strength", type=float, default=0.6)
    parser.add_argument("--gs-iterations", type=int, default=500)
    parser.add_argument("--seed", type=int, default=32)
    parser.add_argument("--prompt", help="Scene/motion instruction; overrides the historical classroom prompt")
    parser.add_argument("--caption-file", type=Path, help="Use this text directly instead of loading the Qwen captioner")
    parser.add_argument("--sampling-steps", type=int, default=50)
    parser.add_argument("--cfg", type=float, default=5.0)
    args = parser.parse_args()
    if args.caption_file:
        args.caption_file = args.caption_file.resolve()
    if args.chunks < 1 or min(args.width, args.height) < 16 or args.width % 16 or args.height % 16:
        parser.error("Use positive chunks and image dimensions divisible by 16")
    if not -90 < args.total_angle_deg < 0:
        parser.error("Choose a left rotation strictly between -90 and 0 degrees")
    if not 0 <= args.strength <= 1 or args.gs_iterations < 1 or args.sampling_steps < 1 or args.cfg < 0:
        parser.error("Invalid strength, GS iterations, sampling steps or CFG")
    input_path = Path(args.image).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.chdir(ROOT / "WorldWarp")

    import imageio.v2 as imageio
    import numpy as np
    import torch
    from PIL import Image, ImageOps
    from omegaconf import OmegaConf
    from pose_control import CONFIG, WanVideoGenerator, seed_everything
    from chunk_trajectory import chunk_pose_bounds, slice_chunk_trajectory

    started = time.monotonic()
    cfg = OmegaConf.create(OmegaConf.to_container(CONFIG, resolve=True))
    cfg.experiment.output_root = str(output / "artifacts")
    cfg.experiment.seed = args.seed
    cfg.loop_params.n_chunks = args.chunks
    cfg.loop_params.output_fps = 30
    cfg.inference_params.update(n_frames=81, context_frames=1, context_frames_2nd=1,
                               width=args.width, height=args.height,
                               minxs=1.0 - args.strength, num_gs_iterations=args.gs_iterations,
                               sampling_timesteps=args.sampling_steps, guidance_scale=args.cfg)
    cfg.camera_pose_control.chunk_poses = [{"pitch": args.total_angle_deg / args.chunks}] * args.chunks
    cfg.prompts.positive = (
        "Photorealistic empty classroom with rows of blue-edged desks and chairs, "
        "green chalkboards and a central display on the front wall, Chinese wall "
        "slogans and a red flag above the boards, fluorescent ceiling lights, "
        "stationary ceiling fans, educational posters, white walls and a gray floor. "
        "Preserve the existing classroom layout, furniture, wall decorations, materials "
        "and lighting. Do not add people or new objects. Everything in the classroom "
        "remains stationary. The camera stays at one fixed position and turns slowly "
        "left at constant angular speed, with no translation, roll, tilt or zoom."
    )
    if args.prompt:
        cfg.prompts.positive = args.prompt
    cfg.video_source.prompt = cfg.prompts.positive
    seed_everything(args.seed)
    torch.cuda.reset_peak_memory_stats()

    with Image.open(input_path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        original_size = list(im.size)
        im = ImageOps.fit(im, (args.width, args.height), method=Image.Resampling.LANCZOS)
        im.save(output / "input_prepared.png")
        first_rgb = np.asarray(im)

    n, context, fps = 81, 1, 30
    total_frames = n + (args.chunks - 1) * (n - context)
    poses_np = constant_y_rotation(total_frames, args.total_angle_deg)
    angular_step_deg = args.total_angle_deg / (total_frames - 1)
    relative_rotations = np.einsum("nji,njk->nik", poses_np[:-1, :3, :3], poses_np[1:, :3, :3])
    np.testing.assert_allclose(relative_rotations,
                               np.broadcast_to(relative_rotations[0], relative_rotations.shape), atol=2e-7)
    assert np.count_nonzero(poses_np[:, :3, 3]) == 0
    generator = WanVideoGenerator(cfg)
    intrinsics = generator.pose_controller.generate_intrinsics(total_frames)
    poses = torch.from_numpy(poses_np).unsqueeze(0)
    np.savez_compressed(output / "requested_camera_trajectory.npz",
                        c2w=poses_np, intrinsics=intrinsics[0].numpy(), fps=fps)
    trajectory_checks = []
    for idx in range(args.chunks):
        cp, _ = slice_chunk_trajectory(poses, intrinsics, idx, n, context)
        offset = 0 if idx == 0 else n - context
        target = cp[0, offset:offset+n].numpy()
        target_start = idx * (n - context)
        np.testing.assert_array_equal(target, poses_np[target_start:target_start+n])
        trajectory_checks.append(dict(chunk=idx, input_window=list(chunk_pose_bounds(idx, n, context)),
                                      target_frames=[target_start, target_start+n-1]))

    report = dict(status="loading_models", input=str(input_path), original_size=original_size,
                  prepared_size=[args.width, args.height], preparation="aspect-preserving center crop",
                  input_sha256=hashlib.sha256(input_path.read_bytes()).hexdigest(),
                  chunks=args.chunks, fps=fps, expected_frames=total_frames,
                  expected_seconds=total_frames/fps, total_angle_deg=args.total_angle_deg,
                  angular_step_deg=angular_step_deg, angular_speed_deg_per_second=angular_step_deg*fps,
                  translation="fixed zero", rotation="constant negative Y rotation (pan left)",
                  strength=args.strength, gs_iterations=args.gs_iterations,
                  seed=args.seed, cuda_visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES"),
                  trajectory_checks=trajectory_checks, completed_chunks=[])
    def save_report():
        (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    save_report()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(np.arange(total_frames)/fps, np.arange(total_frames)*angular_step_deg)
    for idx in range(1, args.chunks):
        ax.axvline(idx*(n-context)/fps, color="gray", linestyle="--", alpha=0.5)
    ax.set(xlabel="Time (s)", ylabel="Camera Y rotation (degrees)",
           title="Constant-speed left turn; camera position fixed")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output / "camera_trajectory.png", dpi=160)
    plt.close(fig)
    generator._load_models()
    if args.caption_file:
        caption = args.caption_file.read_text().strip()
        if not caption:
            raise ValueError("Caption file is empty")
        generator.caption_model = "provided_caption"
        generator.get_caption = lambda **kwargs: caption
    else:
        generator._init_captioner(is_vl=True)
    if generator.caption_model is None:
        raise RuntimeError("Qwen captioner failed to load")
    poses, intrinsics = poses.to(generator.device), intrinsics.to(generator.device)
    source_video = output / "source_81f.mp4"
    with imageio.get_writer(source_video, fps=fps, codec="libx264", quality=9, macro_block_size=1) as writer:
        for _ in range(n):
            writer.append_data(first_rgb)

    previous = str(source_video)
    for idx in range(args.chunks):
        report["status"] = f"generating_chunk_{idx+1}"
        save_report()
        cp, ck = slice_chunk_trajectory(poses, intrinsics, idx, n, context)
        chunk_start = time.monotonic()
        print(f"\n=== GENERATING CHUNK {idx+1}/{args.chunks} ===", flush=True)
        previous = generator.run_inference_chunk(idx, previous, cp, ck, context, idx == 0,
                                                  style_prompt=cfg.prompts.positive)
        reader = imageio.get_reader(previous)
        count = reader.count_frames()
        reader.close()
        if count != n:
            raise RuntimeError(f"Expected {n} chunk frames, got {count}")
        report["completed_chunks"].append(dict(index=idx, path=previous, frames=count,
                                                elapsed_seconds=time.monotonic()-chunk_start))
        save_report()
        torch.cuda.empty_cache()
        print(f"=== COMPLETED CHUNK {idx+1}/{args.chunks} ===", flush=True)

    final_path = output / f"{input_path.stem}_pan_left_{args.chunks}chunks_{total_frames/fps:g}s.mp4"
    written = 0
    with imageio.get_writer(final_path, fps=fps, codec="libx264", quality=9, macro_block_size=1) as writer:
        for item in report["completed_chunks"]:
            reader = imageio.get_reader(item["path"])
            for frame_idx, frame in enumerate(reader):
                if item["index"] == 0 or frame_idx >= context:
                    writer.append_data(frame)
                    written += 1
            reader.close()
    if written != total_frames:
        raise RuntimeError(f"Unexpected final frame count {written}")
    report.update(status="complete", output_video=str(final_path), written_frames=written,
                  elapsed_seconds=time.monotonic()-started,
                  peak_gpu_memory_gib=torch.cuda.max_memory_allocated()/2**30)
    save_report()
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
