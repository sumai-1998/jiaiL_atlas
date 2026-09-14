"""Ensure expanded context preserves genuine history and the final time grid."""
import unittest
from generate_worldwarp_hybrid_context import context_window


class ContextWindowTests(unittest.TestCase):
    def test_context_five_is_actual_previous_history(self):
        for i in (1,2,3):
            w = context_window(i, 5)
            expected = list(range(i*80-4, i*80+1))
            self.assertEqual(w['source'][-5:], expected)
            self.assertEqual(w['target'][:5], expected)
            self.assertEqual(w['poses'][80:], w['target'])
            self.assertEqual(len(w['target']), 85)

    def test_export_has_no_missing_or_duplicate_times(self):
        for context in (1,5,9,25):
            final = []
            for i in range(4):
                w = context_window(i,context)
                delivered = w['target'][w['extra_prefix']:]
                self.assertEqual(len(delivered),81)
                final.extend(delivered if i == 0 else delivered[1:])
            self.assertEqual(final,list(range(321)))

    def test_context_one_matches_original_windows(self):
        for i in range(4):
            w = context_window(i,1)
            self.assertEqual(w['target'],list(range(i*80,i*80+81)))
            expected = list(range(81)) if i == 0 else list(range((i-1)*80,i*80+81))
            self.assertEqual(w['poses'],expected)

    def test_invalid_context_alignment_rejected(self):
        with self.assertRaises(ValueError):
            context_window(1,4)


if __name__ == '__main__':
    unittest.main()
