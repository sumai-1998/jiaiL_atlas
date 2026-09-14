#!/usr/bin/env python3
"""MapAnything RGB -> pointmaps, posed RGB-D, and a voxel-merged point cloud.

This is a local convenience/installation-validation entry, not the AR world loop.
Images can be genuine observations, GS renders, or generated candidates; record
their provenance explicitly with --source-kind.
"""
import argparse
import json
import os
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault("TORCH_HOME",str(ROOT/".cache/torch_geometry"))
os.environ.setdefault("HF_HOME",str(ROOT/"hf_cache"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY","1")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images",nargs="+",required=True,help="Image paths or one image directory")
    parser.add_argument("--output",required=True)
    parser.add_argument("--variant",choices=["default","apache"],default="default")
    parser.add_argument("--source-kind",choices=["observed","rendered","generated","unknown"],default="unknown")
    parser.add_argument("--max-views",type=int,default=8)
    parser.add_argument("--voxel-size",type=float,default=0.02)
    parser.add_argument("--device",default="cuda")
    args=parser.parse_args()
    import numpy as np
    import open3d as o3d
    import torch
    from mapanything.models import MapAnything
    from mapanything.utils.image import load_images

    images=[Path(p).expanduser().resolve() for p in args.images]
    if len(images)==1 and images[0].is_dir():
        images=sorted(p for p in images[0].iterdir() if p.suffix.lower() in (".png",".jpg",".jpeg",".webp"))
    images=images[:args.max_views]
    if not images or not all(p.is_file() for p in images):
        raise ValueError("Provide one or more existing images")
    output=Path(args.output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    if (output/"posed_rgbd.npz").exists():
        raise FileExistsError("Output already contains posed_rgbd.npz; use a new output directory")
    ckpt=ROOT/"checkpoints"/("mapanything" if args.variant=="default" else "mapanything-apache")
    if not (ckpt/"model.safetensors").is_file():
        raise FileNotFoundError(f"Download checkpoint first: {ckpt}")
    if args.device.startswith("cuda"):
        assert torch.cuda.is_available(), "CUDA not available"
        torch.cuda.reset_peak_memory_stats()
    start=time.monotonic()
    print(f"Loading {ckpt}; images={len(images)}",flush=True)
    model=MapAnything.from_pretrained(str(ckpt)).eval().to(args.device)
    views=load_images([str(p) for p in images],verbose=True)
    with torch.inference_mode():
        predictions=model.infer(views,memory_efficient_inference=True,minibatch_size=1,
            use_amp=True,amp_dtype="bf16",apply_mask=True,mask_edges=True,
            apply_confidence_mask=False)
    records=[]
    for pred in predictions:
        to_np=lambda t:t.detach().float().cpu().numpy()
        rgb=to_np(pred["img_no_norm"])[0]
        if rgb.shape[-1]!=3:rgb=rgb.transpose(1,2,0)
        depth=to_np(pred["depth_z"])[0,...,0]
        points=to_np(pred["pts3d"])[0]
        mask=pred["mask"].detach().cpu().numpy()[0,...,0].astype(bool)
        mask &= np.isfinite(depth)&(depth>0)&np.isfinite(points).all(-1)
        records.append(dict(rgb=np.rint(np.clip(rgb,0,1)*255).astype(np.uint8),depth=depth,
            points=points,valid=mask,intrinsics=to_np(pred["intrinsics"])[0],
            c2w=to_np(pred["camera_poses"])[0],confidence=to_np(pred["conf"])[0]))
    if len({r["depth"].shape for r in records})!=1:
        raise ValueError("This convenience exporter requires equal processed image dimensions; group matching aspect ratios")
    stack=lambda key:np.stack([r[key] for r in records])
    np.savez_compressed(output/"posed_rgbd.npz",rgb=stack("rgb"),depth_z=stack("depth"),
        valid=stack("valid"),intrinsics=stack("intrinsics"),c2w=stack("c2w"),confidence=stack("confidence"))
    np.savez_compressed(output/"pointmaps.npz",points=stack("points"),valid=stack("valid"))
    points=np.concatenate([r["points"][r["valid"]] for r in records])
    colors=np.concatenate([r["rgb"][r["valid"]] for r in records])/255.
    if len(points)==0:raise RuntimeError("No valid geometry was produced")
    cloud=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
    cloud.colors=o3d.utility.Vector3dVector(colors)
    if args.voxel_size>0:cloud=cloud.voxel_down_sample(args.voxel_size)
    o3d.io.write_point_cloud(str(output/"pointcloud_fused.ply"),cloud,write_ascii=False)
    report=dict(model=str(ckpt),variant=args.variant,input_images=[str(p) for p in images],
        source_kind=args.source_kind,pose_convention="OpenCV c2w",depth_convention="z-depth",
        scale_source="MapAnything predicted metric scale; not independently calibrated",
        view_count=len(records),processed_hw=list(records[0]["depth"].shape),
        valid_pixels_per_view=[int(r["valid"].sum()) for r in records],
        merged_points=len(cloud.points),voxel_size=args.voxel_size,
        elapsed_seconds=time.monotonic()-start,
        peak_gpu_memory_gib=torch.cuda.max_memory_allocated()/2**30 if args.device.startswith("cuda") else None,
        torch=torch.__version__,cuda=torch.version.cuda,
        caveat="Voxel aggregation in the model's shared coordinate frame; not a persistent SLAM map or quality benchmark")
    (output/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
