#!/usr/bin/env python3
"""Analytic textured-plane RGB-D fixture, solely for installation testing."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',required=True)
a=p.parse_args()
out=Path(a.output).resolve()
if (out/'posed_rgbd.npz').exists():
    raise FileExistsError(out/'posed_rgbd.npz')
out.mkdir(parents=True,exist_ok=True)
h,w=128,192
K=np.array([[160,0,w/2],[0,160,h/2],[0,0,1]],dtype=np.float32)
yy,xx=np.mgrid[:h,:w]
frames=[];poses=[];depths=[]
for idx,tx in enumerate([-0.08,0.,0.08]):
    c2w=np.eye(4,dtype=np.float32);c2w[0,3]=tx
    depth=np.full((h,w),3.,dtype=np.float32)
    world_x=(xx-K[0,2])*3/K[0,0]+tx
    world_y=(yy-K[1,2])*3/K[1,1]
    checker=((np.floor(world_x*5)+np.floor(world_y*5))%2)
    rgb=np.stack([80+120*checker,110+50*np.sin(world_x*4),100+70*np.cos(world_y*5)],-1)
    rgb=np.clip(rgb,0,255).astype(np.uint8)
    Image.fromarray(rgb).save(out/f'fixture_{idx:03d}.png')
    frames.append(rgb);poses.append(c2w);depths.append(depth)
np.savez_compressed(out/'posed_rgbd.npz',rgb=np.stack(frames),depth_z=np.stack(depths),
    intrinsics=np.stack([K]*3),c2w=np.stack(poses),valid=np.ones((3,h,w),dtype=bool))
(out/'provenance.json').write_text(json.dumps(dict(kind='synthetic analytic fixture',
    scene='textured plane at z=3',poses='OpenCV c2w',not_a_reconstruction_benchmark=True),indent=2))
print(out)
