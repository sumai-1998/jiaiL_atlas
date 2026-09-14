"""CPU regression checks for WorldWarp's multi-chunk trajectory indexing."""
import ast
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "WorldWarp"))
from chunk_trajectory import chunk_pose_bounds, slice_chunk_trajectory


class ChunkTrajectoryTests(unittest.TestCase):
    def test_target_frames_and_overlap(self):
        for context in (1, 5, 25):
            frames = torch.arange(81 + 3 * (81 - context)).view(1, -1, 1, 1)
            previous_target = None
            for idx in range(4):
                poses, _ = slice_chunk_trajectory(frames, frames, idx, 81, context)
                offset = 0 if idx == 0 else 81 - context
                target = poses[0, offset:offset + 81, 0, 0]
                expected_start = idx * (81 - context)
                self.assertTrue(torch.equal(target, torch.arange(expected_start, expected_start + 81)))
                if previous_target is not None:
                    self.assertTrue(torch.equal(target[:context], previous_target[-context:]))
                previous_target = target

    def test_short_trajectory_rejected(self):
        frames = torch.zeros(1, 240, 4, 4)
        with self.assertRaises(ValueError):
            slice_chunk_trajectory(frames, frames, 2, 81, 1)

    def test_invalid_context_rejected(self):
        for context in (0, 81):
            with self.assertRaises(ValueError):
                chunk_pose_bounds(1, 81, context)

    def test_gui_preset_and_custom_use_current_chunk(self):
        # Load the actual session methods without importing the GUI and loading its models.
        tree = ast.parse((ROOT / "WorldWarp/gradio_demo.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "VideoGenerationSession")
        names = ("generate_chunks", "generate_custom_chunk")
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
        namespace = dict(os=os, seed_everything=lambda _: None,
                         print=lambda *a, **kw: None, slice_chunk_trajectory=slice_chunk_trajectory)
        exec(compile(ast.Module(body=methods, type_ignores=[]), "<session-methods>", "exec"), namespace)
        for name in names:
            seen = []
            cfg = NS(video_source=NS(), prompts=NS(), experiment=NS(), loop_params=NS(),
                     inference_params=NS(context_frames=1, n_frames=81),
                     camera_pose_control=NS(chunk_poses=[]))
            session = NS(config=cfg, starting_image="stub-image", chunk_movements=[],
                         video_chunks=[], chunk_ctx_log=[], chunk_captions=[], combined_video_path=None)

            def poses():
                p = torch.arange(81 + 80 * (len(session.chunk_movements) - 1)).view(1, -1, 1, 1)
                return p, p.clone()

            def inference(idx, video, p, k, context, first, **kwargs):
                offset = 0 if first else 81 - context
                self.assertTrue(torch.equal(p[0, offset:offset + 81, 0, 0], torch.arange(idx * 80, idx * 80 + 81)))
                seen.append(idx)
                return "stub-video"

            session.generator = NS(device="cpu", _generate_controlled_poses=poses,
                                   run_inference_chunk=inference,
                                   pm=NS(dirs={"captions": "/__unused_worldwarp_test_captions__"}))
            session._image_to_video = lambda _: "stub-input"
            session._stitch_all = lambda: "stub-final"
            session._format_history = session._format_captions = lambda: ""
            if name == "generate_chunks":
                namespace[name](session, "", "", ["TRUCK_LEFT"], 4, 1, 0.6, 500, 32)
            else:
                namespace[name](session, "", "", *([0] * 9), 4, 1, 0.6, 500, 32)
            self.assertEqual(seen, [0, 1, 2, 3])


if __name__ == "__main__":
    unittest.main()
