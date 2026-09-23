"""CPU contracts specific to adapting rolling geometry to the benchmark windows."""
import argparse
from copy import deepcopy
import unittest
from unittest.mock import patch

from worldwarp_rolling_benchmark import METHODS, build_plan, select_sources


class RollingTests(unittest.TestCase):
    def test_history_provenance_and_anchor_replacement(self):
        for anchor in (False, True):
            self.assertEqual(select_sources(0, anchor), [(0,True,None)])
            for chunk in range(1,5):
                rows=select_sources(chunk,anchor)
                self.assertEqual(len(rows),6 if anchor and chunk>1 else 5)
                self.assertEqual(len(set(r[0] for r in rows)),len(rows))
                for global_id,observed,local in rows:
                    if observed:
                        self.assertTrue(anchor);self.assertEqual(global_id,0);self.assertIsNone(local)
                    else:
                        self.assertEqual(global_id,(chunk-1)*44+local)
                        self.assertIn(local,[0,12,24,36,48])
                        self.assertLessEqual(global_id,chunk*44+4)
        with self.assertRaises(ValueError):select_sources(5,False)

    def test_plan_never_runs_game_and_keeps_first_image_calibration(self):
        original=dict(parameters=dict(game_seed=0),notes=[],steps=[
            dict(name='scene_'+name,command=['python','script',name,'--output','scene']+
                 (['--guidance-dir','guidance'] if name=='generate' else []))
            for name in ('prepare','mapanything','scale','game-fit','game-render','generate','image-metrics','pose-metrics')])
        for method in METHODS:
            with patch('worldwarp_hybrid_benchmark.build_plan',return_value=deepcopy(original)):
                plan=build_plan(argparse.Namespace(method=method))
            self.assertEqual(len(plan['steps']),6)
            self.assertNotIn('game',plan['pipeline_definition']['environments'])
            gen=plan['steps'][3]['command']
            self.assertEqual(gen[-2:],['--map-method',method]);self.assertNotIn('--guidance-dir',gen)
            self.assertIn('scene_scale',[s['name'] for s in plan['steps']])
            self.assertEqual(plan['parameters']['original_image_anchor'],method!='map-ww-gs')


if __name__=='__main__':unittest.main()
