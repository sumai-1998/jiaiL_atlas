#!/usr/bin/env python3
"""Small actual CUDA checks. Run separately in the two project environments."""
import argparse
import json
import os
import time
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--project',choices=['mapanything','game'],required=True)
p.add_argument('--output',required=True)
p.add_argument('--lpips',action='store_true')
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
os.environ.setdefault('TORCH_HOME',str(root/'.cache/torch_geometry'))
os.environ.setdefault('TORCH_EXTENSIONS_DIR',str(root/'.cache/torch_extensions_geometry'))
import numpy as np
import torch
import torchvision
import open3d as o3d
start=time.monotonic()
assert torch.cuda.is_available()
x=torch.randn(64,64,device='cuda'); y=x@x.T
assert torch.isfinite(y).all()
record=dict(project=a.project,torch=torch.__version__,torchvision=torchvision.__version__,
    cuda=torch.version.cuda,numpy=np.__version__,open3d=o3d.__version__,
    device=torch.cuda.get_device_name(),visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),
    cuda_matmul_pass=True)
if a.project=='game':
    import faiss
    import diff_gaussian_rasterization._C
    import flashsplat_rasterization._C
    from simple_knn._C import distCUDA2
    pts=torch.randn(128,3,device='cuda')
    distances=distCUDA2(pts)
    assert torch.isfinite(distances).all() and (distances>=0).all()
    resources=faiss.StandardGpuResources()
    index=faiss.GpuIndexFlatL2(resources,16)
    vectors=np.random.default_rng(0).random((100,16),dtype=np.float32)
    index.add(vectors)
    d,j=index.search(vectors[:4],1)
    assert np.array_equal(j[:,0],np.arange(4))
    record.update(faiss=faiss.__version__,faiss_gpu_search_pass=True,
        cuda_extensions_import_pass=True,simple_knn_gpu_pass=True)
else:
    from mapanything.models import MapAnything
    import gsplat
    from gsplat import rasterization
    means=torch.tensor([[0.,0.,2.],[0.15,0.,2.]],device='cuda',requires_grad=True)
    quats=torch.tensor([[1.,0.,0.,0.]]*2,device='cuda')
    scales=torch.full((2,3),.1,device='cuda')
    opacities=torch.full((2,),.8,device='cuda')
    colors=torch.tensor([[1.,0.,0.],[0.,1.,0.]],device='cuda')
    K=torch.tensor([[[80.,0.,32.],[0.,80.,32.],[0.,0.,1.]]],device='cuda')
    rendered,alpha,_=rasterization(means,quats,scales,opacities,colors,
        torch.eye(4,device='cuda')[None],K,64,64)
    rendered.sum().backward()
    assert torch.isfinite(rendered).all() and alpha.max()>.1
    assert means.grad is not None and torch.isfinite(means.grad).all()
    record.update(mapanything_import_pass=True,gsplat=gsplat.__version__,
        gsplat_cuda_forward_backward_pass=True)
if a.lpips:
    from torchmetrics.image.lpip import LearnedPerceptualImagePatchSimilarity
    metric=LearnedPerceptualImagePatchSimilarity(net_type='alex',normalize=True).cuda()
    im=torch.rand(1,3,64,64,device='cuda')
    with torch.no_grad():score=metric(im,im).item()
    assert abs(score)<1e-5
    record.update(lpips_alexnet_gpu_pass=True,lpips_identical_score=score)
torch.cuda.synchronize()
record['elapsed_seconds']=time.monotonic()-start
out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2),flush=True)
