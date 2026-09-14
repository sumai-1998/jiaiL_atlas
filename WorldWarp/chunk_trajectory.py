"""Select the previous/current frame window used by WorldWarp chunk inference."""


def chunk_pose_bounds(chunk_idx, n_frames, context_frames):
    if chunk_idx < 0 or n_frames < 2 or not 1 <= context_frames < n_frames:
        raise ValueError("Invalid chunk index, frame count, or context count")
    if chunk_idx == 0:
        return 0, n_frames
    start = (chunk_idx - 1) * (n_frames - context_frames)
    return start, start + 2 * n_frames - context_frames


def slice_chunk_trajectory(poses, intrinsics, chunk_idx, n_frames, context_frames):
    start, end = chunk_pose_bounds(chunk_idx, n_frames, context_frames)
    if poses.shape[1] < end or intrinsics.shape[1] < end:
        raise ValueError(f"Chunk {chunk_idx} needs trajectory frames [{start}:{end}]")
    return poses[:, start:end].clone(), intrinsics[:, start:end].clone()
