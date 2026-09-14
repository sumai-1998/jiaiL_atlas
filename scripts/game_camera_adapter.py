"""Local GaME camera adapter for arbitrary zero-skew OpenCV intrinsics.

No upstream file edits. Fixes the native helper's centered-principal-point
assumption and accounts for the rasterizer's ndc2Pix half-pixel convention.
"""
import numpy as np
import torch
from src.utils import utils

_native_camera=utils.flashsplat_cam

def calibrated_camera(color,depth,segmentation,K,w2c,uid):
    camera=_native_camera(color,depth,segmentation,K,w2c,uid)
    h,w=color.shape[-2:]
    assert abs(K[0,1])<1e-6 and abs(K[1,0])<1e-6, 'Nonzero skew is unsupported'
    fx,fy,cx,cy=float(K[0,0]),float(K[1,1]),float(K[0,2]),float(K[1,2])
    assert fx>0 and fy>0
    camera.FoVx=2*np.arctan(w/(2*fx))
    camera.FoVy=2*np.arctan(h/(2*fy))
    P=camera.projection_matrix.T.clone()
    P[0,0]=2*fx/w;P[1,1]=2*fy/h
    P[0,2]=(2*cx+1)/w-1;P[1,2]=(2*cy+1)/h-1
    camera.projection_matrix=P.T.contiguous()
    camera.full_proj_transform=camera.world_view_transform@camera.projection_matrix
    return camera

def install_and_check():
    utils.flashsplat_cam=calibrated_camera
    h,w=64,96
    K=np.array([[70.,0.,41.2],[0.,72.,28.1],[0.,0.,1.]])
    w2c=torch.eye(4);w2c[0,3]=-.15
    camera=calibrated_camera(torch.zeros(3,h,w,device='cuda'),torch.ones(h,w,device='cuda'),None,K,w2c,0)
    pts=torch.tensor([[0.,0.,2.,1.],[.2,-.1,3.,1.]],device='cuda')
    clip=pts@camera.full_proj_transform
    ndc=clip[:,:2]/clip[:,3:4]
    pixels=((ndc+1)*torch.tensor([w,h],device='cuda')-1)/2
    cam=pts@w2c.T.cuda()
    expected=cam[:,:3]@torch.tensor(K,dtype=torch.float32,device='cuda').T
    expected=expected[:,:2]/expected[:,2:3]
    error=float((pixels-expected).abs().max())
    assert error<1e-3, error
    return error
