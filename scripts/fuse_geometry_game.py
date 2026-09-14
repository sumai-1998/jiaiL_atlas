#!/usr/bin/env python3
"""Fuse a MapAnything posed_rgbd.npz into a small GaME scene.

Installation/static-scene adapter. Uses a single full-frame static mask by
default, NOT a SAM result or an automatic moving-object detector.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"GaME"))
os.environ.setdefault("WANDB_MODE","disabled")
os.environ.setdefault("TORCH_HOME",str(ROOT/".cache/torch_geometry"))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rgbd",required=True,help="posed_rgbd.npz from run_mapanything.sh")
    parser.add_argument("--output",required=True)
    parser.add_argument("--max-views",type=int,default=3)
    parser.add_argument("--max-width",type=int,default=224,help="Small default for installation validation")
    parser.add_argument("--iterations",type=int,default=20,help="Extra GaME keyframe iterations; native train also does 50 warmup steps")
    args=parser.parse_args()
    import cv2
    import numpy as np
    import torch
    import yaml
    from PIL import Image
    from src.entities.game import GaME
    from src.flashsplat.gaussian_renderer import flashsplat_render
    from src.utils import utils
    from game_camera_adapter import install_and_check

    assert torch.cuda.is_available(), "GaME needs CUDA"
    utils.setup_seed(0)
    torch.cuda.reset_peak_memory_stats()
    camera_projection_error=install_and_check()
    input_path=Path(args.rgbd).resolve()
    output=Path(args.output).resolve()
    if (output/"gaussians.ply").exists():
        raise FileExistsError("Use a new output directory to preserve an existing scene")
    output.mkdir(parents=True,exist_ok=True)
    package=np.load(input_path,allow_pickle=False)
    count=min(args.max_views,len(package["rgb"]))
    samples=[]
    for i in range(count):
        image=package["rgb"][i]
        depth=package["depth_z"][i].astype(np.float32).copy()
        valid=package["valid"][i].astype(bool)
        depth[~valid]=0
        old_h,old_w=depth.shape
        ratio=min(1.,args.max_width/old_w)
        w,h=round(old_w*ratio),round(old_h*ratio)
        K=package["intrinsics"][i].astype(np.float64).copy()
        K[0,:]*=w/old_w;K[1,:]*=h/old_h
        image=cv2.resize(image,(w,h),interpolation=cv2.INTER_AREA)
        depth=cv2.resize(depth,(w,h),interpolation=cv2.INTER_NEAREST)
        # Native GaME actual code/data loaders use WORLD-TO-CAMERA. Some upstream
        # comments incorrectly call this field c2w; the shared package is c2w.
        pose=np.linalg.inv(package["c2w"][i]).astype(np.float32)
        samples.append(dict(color=image,depth=depth,pose=pose,intrinsics=K,
                            masks=torch.ones((1,h,w),dtype=torch.bool)))

    class FrameDataset:
        start_frame=0
        run_id="static_npz"
        def __len__(self):return len(samples)
        def __getitem__(self,index):return samples[index]

    config=yaml.safe_load((ROOT/"GaME/configs/flat/flat.yaml").read_text())["game"]
    config.update(first_keyframe_iters=args.iterations,keyframe_iters=args.iterations,
                  refinement_iters=0,scale=1.,keyframe_translation_diff=0.,num_label_channels=256)
    # Zero camera motion can occur in a static installation fixture; keep the
    # unmodified native selector and record accepted keyframe count explicitly.
    start=time.monotonic()
    class TracedGaME(GaME):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw)
            self.seed_events=[]
        def _add_gaussians(self,*a,**kw):
            before=len(self.gaussian_model.get_xyz)
            result=super()._add_gaussians(*a,**kw)
            after=len(self.gaussian_model.get_xyz)
            self.seed_events.append(dict(frame_id=len(self.estimated_poses)-1,
                before_seeding=before,after_seeding=after,new_seeds=after-before))
            return result
    model=TracedGaME(config,wandb_online=False)
    dataset=FrameDataset()
    model.train(dataset,output/dataset.run_id)
    xyz=model.gaussian_model.get_xyz.detach()
    if xyz.numel()==0 or not torch.isfinite(xyz).all():
        raise RuntimeError("GaME produced an empty/non-finite Gaussian map")
    model.gaussian_model.save_ply(str(output/"gaussians.ply"))
    model.save(output,{"dataset_path":str(input_path),"dataset_name":"static_npz_install_adapter"})
    rendered=[]
    for idx,sample in enumerate(samples):
        view=utils.flashsplat_cam(torch.from_numpy(sample["color"].copy()).permute(2,0,1).float().cuda()/255,
            torch.from_numpy(sample["depth"]).cuda(),None,sample["intrinsics"],torch.from_numpy(sample["pose"]),idx)
        with torch.no_grad():
            render=flashsplat_render(view,model.gaussian_model,utils.flashsplat_pipe(),torch.zeros(3,device="cuda"),obj_num=256)
        rgb=render["render"].detach().clamp(0,1).permute(1,2,0).cpu().numpy()
        if not np.isfinite(rgb).all():raise RuntimeError("Non-finite GS render")
        Image.fromarray((rgb*255).astype(np.uint8)).save(output/f"render_{idx:03d}.png")
        rendered.append(dict(frame=idx,mean_alpha=float(render["alpha"].mean()),mean_rgb=float(rgb.mean())))
    count_before=len(xyz)
    seed_events=model.seed_events
    del xyz,view,render,model
    torch.cuda.empty_cache()
    restored=GaME(config,wandb_online=False,checkpoint_path=output/"checkpoints/checkpoint.pth",all_train_data=[dataset])
    assert len(restored.gaussian_model.get_xyz)==count_before
    report=dict(input=str(input_path),input_views=len(samples),keyframes=len(restored.keyframes),
        gaussians=count_before,checkpoint_reload_pass=True,rendered=rendered,
        seed_events=seed_events,
        elapsed_seconds=time.monotonic()-start,peak_gpu_memory_gib=torch.cuda.max_memory_allocated()/2**30,
        input_pose="OpenCV c2w",game_pose="w2c (explicit inverse)",
        camera_adapter="Full zero-skew K including principal point; no upstream edits",
        camera_projection_test_max_error_px=camera_projection_error,
        masks="Single full-frame static mask: NOT SAM / motion segmentation",
        config=config,torch=torch.__version__,cuda=torch.version.cuda,
        caveat="Static installation/fusion smoke test, not the complete Atlas AR loop or dynamic-scene benchmark")
    (output/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
