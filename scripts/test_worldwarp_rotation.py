"""CPU checks for the constant-speed left-turn camera conditioning."""
import sys
import unittest
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "WorldWarp"))
from chunk_trajectory import slice_chunk_trajectory
from generate_worldwarp_rotation import constant_y_rotation


class RotationTests(unittest.TestCase):
    def setUp(self):
        self.poses = constant_y_rotation(321, -20)
        self.rotations = self.poses[:, :3, :3].astype(float)

    def test_fixed_position_and_uniform_angle(self):
        np.testing.assert_array_equal(self.poses[:, :3, 3], 0)
        angles = np.rad2deg(np.arctan2(self.rotations[:, 0, 2], self.rotations[:, 0, 0]))
        np.testing.assert_allclose(angles[[0, -1]], [0, -20], atol=1e-6)
        np.testing.assert_allclose(np.diff(angles), -0.0625, atol=3e-6)

    def test_valid_rotations(self):
        r = self.rotations
        np.testing.assert_allclose(np.einsum("nji,njk->nik", r, r),
                                   np.broadcast_to(np.eye(3), r.shape), atol=1e-7)
        np.testing.assert_allclose(np.linalg.det(r), 1, atol=1e-7)

    def test_left_turn_projection(self):
        # Optical axis moves toward negative X; a stationary front point moves right.
        self.assertTrue((self.rotations[1:, 0, 2] < 0).all())
        camera_points = np.einsum("nji,j->ni", self.rotations, np.array([0, 0, 3.0]))
        self.assertTrue((np.diff(camera_points[:, 0] / camera_points[:, 2]) > 0).all())

    def test_four_chunk_continuity(self):
        poses = torch.from_numpy(self.poses).unsqueeze(0)
        for idx in range(4):
            chunk, _ = slice_chunk_trajectory(poses, poses, idx, 81, 1)
            offset = 0 if idx == 0 else 80
            np.testing.assert_array_equal(chunk[0, offset:offset+81], self.poses[idx*80:idx*80+81])


if __name__ == "__main__":
    unittest.main()
