"""CPU checks for dataset camera conversion, crop and benchmark frame mapping."""
import sys
from pathlib import Path
import unittest
import argparse
import json
import tempfile
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'WorldWarp'))
from worldwarp_benchmark import decode_cameras,crop_transform,N_FRAMES
from worldwarp_benchmark import build_plan
from chunk_trajectory import chunk_pose_bounds
from worldwarp_benchmark_metrics import frechet_low_rank,pose_distances


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_routes_frozen_scenes_and_rejects_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shard=root/'source.torch';shard.touch()
            manifest=root/'inventory.json'
            manifest.write_text(json.dumps({'scenes':[dict(scene_id=x*64,format='pixelsplat_torch',
                frames=300,shard_path=str(shard)) for x in ('b','a','c')]}))
            args=argparse.Namespace(output=root/'new',manifest=manifest,count=3,gpu='0',dust3r_root=root/'dust3r')
            plan=build_plan(args)
            self.assertEqual([s['scene_id'][0] for s in plan['inputs']],['a','b','c'])
            self.assertEqual(len(plan['steps']),16)
            self.assertEqual(plan['parameters']['endpoint_indices_zero_based'],[49,199])
            self.assertFalse(args.output.exists())
            args.output.mkdir()
            with self.assertRaises(FileExistsError):build_plan(args)

    def test_camera_extrinsics_are_inverted_and_rebased(self):
        c=np.zeros((2,18));c[:,:4]=[1,2,.5,.5]
        w=np.tile(np.eye(4),(2,1,1));w[0,0,3]=-2;w[1,0,3]=-3
        c[:,6:]=w[:,:3].reshape(2,12)
        poses,k=decode_cameras(c,480,270)
        np.testing.assert_allclose(poses[0],np.eye(4))
        np.testing.assert_allclose(poses[1,:3,3],[1,0,0])
        np.testing.assert_allclose(k[0],[[480,0,240],[0,540,135],[0,0,1]])

    def test_crop_preserves_projected_rays(self):
        (rw,rh,x,y),a=crop_transform(480,270)
        k=np.array([[500,0,239.5],[0,490,134.5],[0,0,1]])
        ray=np.array([.2,-.1,1.])
        old=k@ray
        expected=np.array([(old[0]+.5)*rw/480-.5-x,(old[1]+.5)*rh/270-.5-y,1.])
        np.testing.assert_allclose(a@k@ray,expected)

    def test_paper_chunks_reach_endpoints_without_gap(self):
        delivered=[]
        for i in range(5):
            start,end=chunk_pose_bounds(i,49,5)
            ids=list(range(start,end))
            target=ids if i==0 else ids[44:]
            self.assertEqual(target,list(range(i*44,i*44+49)))
            delivered+=target if i==0 else target[5:]
        self.assertEqual(delivered,list(range(N_FRAMES)))
        self.assertIn(49,delivered);self.assertIn(199,delivered)

    def test_fid_matches_dense_covariance_and_handles_rank_deficiency(self):
        from scipy.linalg import sqrtm
        rng=np.random.default_rng(7)
        x,y=rng.normal(size=(12,4)),rng.normal(size=(15,4))
        a,b=np.cov(x,rowvar=False),np.cov(y,rowvar=False)
        expected=np.sum((x.mean(0)-y.mean(0))**2)+np.trace(a+b-2*sqrtm(a@b))
        self.assertAlmostEqual(frechet_low_rank(x,y),float(expected),places=10)
        z=rng.normal(size=(3,2048))
        self.assertAlmostEqual(frechet_low_rank(z,z),0,places=8)

    def test_pose_metric_removes_origin_and_scale_not_wrong_direction(self):
        gt=np.tile(np.eye(4),(3,1,1));gt[:,0,3]=[1,2,3]
        pred=gt.copy();pred[:,:3,3]*=7
        r,t,_=pose_distances(pred,gt)
        np.testing.assert_allclose(r,0);np.testing.assert_allclose(t,0)
        pred[:,0,3]*=-1
        _,t,_=pose_distances(pred,gt)
        self.assertAlmostEqual(t[-1],2)


if __name__=='__main__':unittest.main()
