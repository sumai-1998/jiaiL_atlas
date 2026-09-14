"""Check projection direction and motion compensation against analytic cases."""
import unittest
import numpy as np
from compare_worldwarp_hybrid import rotation_homography, warp_and_mask, reference_scores


class ComparisonGeometryTests(unittest.TestCase):
    def test_left_turn_moves_center_ray_right(self):
        angle = np.deg2rad(-20.)
        target = np.eye(4)
        target[:3, :3] = [[np.cos(angle), 0, np.sin(angle)], [0, 1, 0],
                          [-np.sin(angle), 0, np.cos(angle)]]
        k = np.array([[576., 0, 240], [0, 576, 304], [0, 0, 1]])
        hom = rotation_homography(np.eye(4), target, k, k)
        pixel = hom @ [240., 304., 1.]
        np.testing.assert_allclose(pixel[:2]/pixel[2],
                                   [240+576*np.tan(np.deg2rad(20)), 304], atol=1e-9)

    def test_known_pixel_motion_is_removed(self):
        rng = np.random.default_rng(10)
        source = rng.integers(0, 256, size=(60, 80, 3), dtype=np.uint8)
        hom = np.array([[1., 0, 3], [0, 1, 0], [0, 0, 1]])
        predicted, valid = warp_and_mask(source, hom, (80, 60))
        target = np.zeros_like(source)
        target[:, 3:] = source[:, :-3]
        np.testing.assert_array_equal(predicted[valid], target[valid])
        self.assertFalse(valid[:, :10].any())
        scores = reference_scores(target, predicted, valid)
        self.assertEqual(scores['known_rgb_mae_255'], 0.)
        self.assertAlmostEqual(scores['known_luma_ssim'], 1.)

    def test_translation_is_rejected(self):
        translated = np.eye(4)
        translated[0, 3] = 1
        with self.assertRaises(AssertionError):
            rotation_homography(np.eye(4), translated, np.eye(3), np.eye(3))


if __name__ == '__main__':
    unittest.main()
