"""CPU contracts for paired inputs, geometry provenance and SE3 benchmark windows."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from worldwarp_hybrid_benchmark import build_plan,depth_scale,target_global_indices


class HybridBenchmarkTests(unittest.TestCase):
    def test_guidance_windows_match_global_trajectory_and_continuous_context(self):
        delivered=[]
        previous=None
        for chunk in range(5):
            ids=target_global_indices(chunk,np.arange(49) if chunk==0 else np.arange(44,93))
            np.testing.assert_array_equal(ids,np.arange(chunk*44,chunk*44+49))
            if previous is not None:
                np.testing.assert_array_equal(ids[:5],previous[-5:])
            delivered.extend(ids if chunk==0 else ids[5:])
            previous=ids
        self.assertEqual(delivered,list(range(225)))
        with self.assertRaises(ValueError):target_global_indices(1,np.arange(49))

    def test_depth_unit_scale_uses_only_valid_positive_pixels(self):
        source=np.linspace(1,6,400).reshape(20,20)
        target=source*3.25
        valid=np.ones_like(source,dtype=bool)
        target[0,:]=np.nan
        source[1,:]=-1
        valid[2,:]=False
        factor,mask=depth_scale(source,target,valid)
        self.assertAlmostEqual(factor,3.25)
        self.assertEqual(int(mask.sum()),340)
        np.testing.assert_allclose((source*factor)[mask],target[mask])
        with self.assertRaises(ValueError):depth_scale(source,target,np.zeros_like(valid))

    def test_hybrid_plan_keeps_baseline_protocol_and_separates_environments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'baseline';base.mkdir()
            shard=root/'shard.torch';shard.touch()
            entries=[dict(scene_id=c*64,format='pixelsplat_torch',frames=225,shard_path=str(shard)) for c in 'ab']
            manifest=root/'manifest.json';manifest.write_text(json.dumps(dict(scenes=entries)))
            params=dict(width=720,height=480,chunks=5,chunk_frames=49,overlap=5,strength=.8,
                        sampling_steps=50,gs_iterations=500,cfg=5,seed=32,delivered_frames=225)
            (base/'status.json').write_text(json.dumps(dict(status='complete',pipeline='ww-dl3dv-benchmark')))
            records=[]
            for item in entries:
                sid=item['scene_id'];folder=base/sid[:12];folder.mkdir();(folder/'gt').mkdir()
                for name in ('gt/00000.png','reference_ttt3r_cameras.npz','dataset_cameras.npz',
                             'image_metrics.json','pose_metrics.json','inception_features.npz'):
                    (folder/name).touch()
                (folder/'data.json').write_text(json.dumps(dict(scene_id=sid)))
                records.append(dict(scene_id=sid,folder=folder.name))
            summary=dict(status='complete',parameters=params,scenes=records)
            (base/'metrics_summary.json').write_text(json.dumps(summary))
            args=argparse.Namespace(manifest=manifest,count=2,output=root/'new',gpu='5',
                                    dust3r_root=root/'dust3r',baseline_runs=[base])
            plan=build_plan(args)
            self.assertEqual(plan['pipeline'],'map-game-ww-dl3dv-benchmark')
            self.assertEqual(len(plan['steps']),17)
            self.assertFalse(args.output.exists())
            self.assertEqual(plan['parameters']['strength'],.8)
            self.assertEqual(plan['parameters']['context_frames_2nd'],5)
            first=plan['steps'][:8]
            self.assertEqual([s['environment'] for s in first],
                             ['worldwarp','mapanything','worldwarp','game','game','worldwarp','worldwarp','worldwarp'])
            self.assertIn('--motion-mode',first[4]['command'])
            self.assertEqual(first[4]['command'][-1],'se3')
            self.assertIn('--guidance-dir',first[5]['command'])
            self.assertNotIn('DIAGNOSTIC_ONLY',json.dumps(plan['steps']))
            summary['parameters']['strength']=.6
            (base/'metrics_summary.json').write_text(json.dumps(summary))
            with self.assertRaisesRegex(ValueError,'protocol mismatch'):build_plan(args)


if __name__=='__main__':unittest.main()
