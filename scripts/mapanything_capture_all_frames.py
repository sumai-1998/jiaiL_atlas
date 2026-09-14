#!/usr/bin/env python3
"""Diagnostic MapAnything inference for every delivered frame, in small windows.

These extra estimates are not fed back into video generation. Window membership
is explicit because multi-view predictions depend on the other input views.
"""
import argparse
import json
import time
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--variant-output',required=True,type=Path)
    p.add_argument('--window',type=int,default=5)
    args=p.parse_args()
    import cv2
    import numpy as np
    import torch
    from mapanything.models import MapAnything
    from mapanything.utils.image import preprocess_inputs
    from classroom_geometry_trace import save_map_native
    torch.set_num_threads(4);cv2.setNumThreads(4)
    torch.manual_seed(32);torch.cuda.manual_seed_all(32)
    root=Path(__file__).resolve().parents[1]
    source=args.variant_output.resolve()
    report=json.loads((source/'report.json').read_text())
    cameras=np.load(source/'requested_camera_trajectory.npz')
    out=source/'mapanything_all_generated_frames';out.mkdir(exist_ok=False)
    frames=[]
    reader=cv2.VideoCapture(report['output_video'])
    if not reader.isOpened():
        raise RuntimeError('Unable to open completed video')
    while True:
        ok,frame=reader.read()
        if not ok:break
        frames.append(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
    reader.release()
    assert len(frames)==321
    model=MapAnything.from_pretrained(str(root/'checkpoints/mapanything')).eval().cuda()
    started=time.monotonic();rows=[]
    for start in range(0,len(frames),args.window):
        ids=list(range(start,min(start+args.window,len(frames))))
        directory=out/f'window_{start:03d}';directory.mkdir()
        inputs=[dict(img=frames[i],intrinsics=cameras['intrinsics'][i],camera_poses=cameras['c2w'][i],
                     is_metric_scale=False) for i in ids]
        views=preprocess_inputs(inputs,resize_mode='fixed_size',size=(406,518),verbose=False)
        with torch.inference_mode():
            predictions=model.infer(views,memory_efficient_inference=True,minibatch_size=1,
                use_amp=True,amp_dtype='bf16',apply_mask=True,mask_edges=False,
                apply_confidence_mask=False,ignore_pose_scale_inputs=True)
        save_map_native(directory/'native.npz',predictions,views,ids)
        np.savez_compressed(directory/'input.npz',rgb=np.stack([frames[i] for i in ids]),
            frame_ids=ids,c2w=cameras['c2w'][ids],intrinsics=cameras['intrinsics'][ids])
        rows.extend(dict(global_frame=i,window_start=start,view_index=j) for j,i in enumerate(ids))
        (out/'progress.json').write_text(json.dumps(dict(status='running',frames_completed=len(rows),total=321)))
        print(f'ALL-FRAME MAP {source.name}: {len(rows)}/321',flush=True)
        del predictions,views
    (out/'manifest.json').write_text(json.dumps(dict(status='complete',frames=321,window=args.window,
        elapsed_seconds=time.monotonic()-started,source_video=report['output_video'],frame_index=rows,
        note='Supplementary inference on decoded delivered video. These predictions were NOT used to generate it; actual pipeline inputs and predictions are stored separately in geometry/chunk_*/.'),indent=2))
    (out/'progress.json').write_text(json.dumps(dict(status='complete',frames_completed=321,total=321)))


if __name__=='__main__':main()
