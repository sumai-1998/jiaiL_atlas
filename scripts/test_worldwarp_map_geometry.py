"""Check camera geometry and source provenance before expensive generation."""
import unittest
import numpy as np
import torch
from worldwarp_map_geometry import select_history, splat_points, unproject_sources, rotation_source_support
from generate_worldwarp_hybrid_context import context_window


class GeometryTests(unittest.TestCase):
    def test_rotation_visibility_rejects_translation(self):
        pose = np.eye(4, dtype=np.float32)
        valid = np.ones((1, 24, 32), bool)
        k = np.array([[30, 0, 16], [0, 30, 12], [0, 0, 1]], np.float32)
        mask = rotation_source_support(pose[None], k[None], valid, pose, k)
        np.testing.assert_array_equal(mask, 1)
        translated = pose.copy()
        translated[0, 3] = .1
        with self.assertRaises(ValueError):
            rotation_source_support(pose[None], k[None], valid, translated, k)

    def test_only_real_previous_history_and_observed_anchor(self):
        for chunk in range(1, 4):
            for anchored in (False, True):
                selected = select_history(chunk, anchored)
                window = context_window(chunk, 5)
                for frame, observed, local in selected:
                    if observed:
                        self.assertEqual(frame, 0)
                        self.assertIsNone(local)
                    else:
                        self.assertEqual(window['source'][local+4], frame)
                        self.assertLessEqual(frame, chunk*80)
                self.assertEqual(len({r[0] for r in selected}), len(selected))

    def test_identity_projection_preserves_colors(self):
        h, w = 24, 32
        rgb = np.random.default_rng(3).integers(0, 256, (1, h, w, 3), dtype=np.uint8)
        k = np.array([[30, 0, w/2], [0, 30, h/2], [0, 0, 1]], dtype=np.float32)
        pose = np.eye(4, dtype=np.float32)
        data = dict(rgb=rgb, depth_z=np.full((1, h, w), 4, dtype=np.float32),
                    valid=np.ones((1, h, w), bool), intrinsics=k[None], c2w=pose[None])
        points, colors = unproject_sources(data, 'cpu')[0]
        image, mask = splat_points(points, colors, torch.from_numpy(pose), torch.from_numpy(k), h, w)
        np.testing.assert_allclose(image.numpy(), rgb[0]/255., atol=2e-6)
        np.testing.assert_allclose(mask.numpy(), 1, atol=2e-6)

    def test_translation_direction_and_occlusion(self):
        pose, k = torch.eye(4), torch.tensor([[10., 0, 4], [0, 10, 4], [0, 0, 1]])
        points = torch.tensor([[0., 0, 2], [0, 0, 4]])
        colors = torch.tensor([[1., 0, 0], [0, 0, 1]])
        image, mask = splat_points(points, colors, pose, k, 9, 9)
        torch.testing.assert_close(image[4, 4], colors[0])
        self.assertEqual(mask[4, 4].item(), 1)
        pose[0, 3] = .2
        image, mask = splat_points(points[:1], colors[:1], pose, k, 9, 9)
        torch.testing.assert_close(image[4, 3], colors[0])
        self.assertEqual(mask[4, 4].item(), 0)


if __name__ == '__main__':
    unittest.main()
