#!/usr/bin/env python3
"""Assemble five completed variants and their already-computed comparisons."""
import argparse
import csv
import json
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from compare_worldwarp_hybrid import rotation_homography, warp_and_mask, gray


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--original', required=True, type=Path)
    p.add_argument('--previous', required=True, type=Path)
    args = p.parse_args()
    cv2.setNumThreads(4)
    root, original, previous = args.root.resolve(), args.original.resolve(), args.previous.resolve()
    out = root / 'overview'
    out.mkdir(exist_ok=True)
    dirs = dict(original=original, hybrid_previous=previous,
                context_5=root/'context_5', strength_050=root/'strength_050', strength_065=root/'strength_065')
    labels = dict(original='WorldWarp only', hybrid_previous='Hybrid: strength 0.60 / context 1',
                  context_5='Hybrid: strength 0.60 / context 5', strength_050='Hybrid: strength 0.50 / context 1',
                  strength_065='Hybrid: strength 0.65 / context 1')
    reports = {key:json.loads((directory/'report.json').read_text()) for key,directory in dirs.items()}
    assert all(r['status']=='complete' for r in reports.values())
    old_comparison = previous.parent/'comparison'
    old = json.loads((old_comparison/'comparison.json').read_text())
    old_rows = json.loads((old_comparison/'per_frame.json').read_text())
    metrics = {key:old['metrics'][source] for key,source in [('original','baseline'),('hybrid_previous','hybrid')]}
    rows = {key:old_rows[source] for key,source in [('original','baseline'),('hybrid_previous','hybrid')]}
    joins = {key:old['joins'][source] for key,source in [('original','baseline'),('hybrid_previous','hybrid')]}
    chunks = {key:old['chunks'][source] for key,source in [('original','baseline'),('hybrid_previous','hybrid')]}
    for key in ('context_5','strength_050','strength_065'):
        comparison = root/'comparisons'/key
        data = json.loads((comparison/'comparison.json').read_text())
        metrics[key], joins[key], chunks[key] = data['metrics']['hybrid'],data['joins']['hybrid'],data['chunks']['hybrid']
        rows[key] = json.loads((comparison/'per_frame.json').read_text())['hybrid']
    summary = dict(labels=labels, videos={key:r['output_video'] for key,r in reports.items()},
                   metrics=metrics, joins=joins, chunks=chunks,
                   note='One fixed image, geometry scene, camera grid and initial seed. Context 5 uses 85-frame internal windows after chunk 1, changing noise placement; no single metric measures overall quality.')
    (out/'metrics.json').write_text(json.dumps(summary,indent=2))
    flat = []
    for key in dirs:
        row = dict(variant=key, label=labels[key], strength=reports[key]['strength'],
                   context_frames_2nd=reports[key].get('context_frames_2nd',1))
        row.update({name:value['mean'] for name,value in metrics[key].items()})
        row['fourth_chunk_temporal_mae'] = chunks[key][3]['motion_compensated_luma_mae_255']['mean']
        row['last_join_temporal_mae'] = joins[key][-1]['motion_compensated_luma_mae_255']
        flat.append(row)
    with (out/'metrics.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    reference=np.array(Image.open(original/'input_prepared.png').convert('RGB'))
    trajectory=np.load(original/'requested_camera_trajectory.npz')
    for directory in dirs.values():
        t=np.load(directory/'requested_camera_trajectory.npz')
        for field in ('c2w','intrinsics','fps'):np.testing.assert_array_equal(t[field],trajectory[field])
        np.testing.assert_array_equal(reference,np.array(Image.open(directory/'input_prepared.png')))
    poses, ks = trajectory['c2w'],trajectory['intrinsics']
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    readers={key:cv2.VideoCapture(r['output_video']) for key,r in reports.items()}
    region_rows={key:[] for key in readers}
    previous_frames={}
    selected={0,80,81,160,161,240,241,320}
    overview_path=out/'classroom_five_versions_10.7s.mp4'
    with imageio.get_writer(overview_path,fps=30,codec='libx264',quality=9,macro_block_size=1) as writer:
        for idx in range(321):
            frames={}
            for key,reader in readers.items():
                ok,bgr=reader.read();assert ok
                frames[key]=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
            H=rotation_homography(poses[0],poses[idx],ks[0],ks[idx])
            reference_view,known_mask=warp_and_mask(reference,H,(480,608))
            source_support=cv2.warpPerspective(np.ones((608,480),np.uint8),H,(480,608),flags=cv2.INTER_NEAREST)
            novel_mask=cv2.erode(1-source_support,np.ones((15,15),np.uint8),
                                  borderType=cv2.BORDER_CONSTANT,borderValue=0).astype(bool)
            if idx:
                relative=rotation_homography(poses[idx-1],poses[idx],ks[idx-1],ks[idx])
                for key,rgb in frames.items():
                    warped_previous,overlap=warp_and_mask(previous_frames[key],relative,(480,608))
                    residual=np.abs(gray(rgb)-gray(warped_previous))
                    novel_valid=novel_mask & overlap
                    region_rows[key].append(dict(frame=idx,time_seconds=idx/30,
                        known_temporal_mae=float(residual[known_mask & overlap].mean()),
                        novel_temporal_mae=float(residual[novel_valid].mean()) if novel_valid.sum()>=128 else None,
                        novel_fraction=float(novel_valid.mean())))
            previous_frames=frames.copy()
            frames['reference']=reference_view
            panel=Image.new('RGB',(1440,1312),'#191d25');draw=ImageDraw.Draw(panel)
            for n,(key,rgb) in enumerate(frames.items()):
                x,y=(n%3)*480,(n//3)*656
                panel.paste(Image.fromarray(rgb),(x,y+48))
                label=labels.get(key,'Projected input: known area only')
                draw.text((x+10,y+5),label,font=font,fill='white')
                draw.text((x+10,y+26),f'{idx/30:5.2f}s | left turn {idx/16:5.2f} deg',font=font,fill='#a8b9cb')
            writer.append_data(np.asarray(panel))
            if idx in selected:
                panel.save(out/f'frame_{idx:03d}.jpg',quality=96)
            if idx in (240,320):
                # Same target-image crop for every version; source reference is
                # also included so edge displacement and detail loss are visible.
                boxes=[(250,130,480,240),(240,390,480,608)]
                detail=Image.new('RGB',(6*320,2*328),'#191d25');d=ImageDraw.Draw(detail)
                for n,(key,rgb) in enumerate(frames.items()):
                    for ri,box in enumerate(boxes):
                        crop=ImageOps.contain(Image.fromarray(rgb).crop(box),(320,280),Image.Resampling.LANCZOS)
                        x,y=n*320,ri*328
                        detail.paste(crop,(x+(320-crop.width)//2,y+48))
                        short={'original':'WorldWarp','hybrid_previous':'Hybrid 0.60 / ctx 1','context_5':'Hybrid 0.60 / ctx 5',
                               'strength_050':'Hybrid 0.50 / ctx 1','strength_065':'Hybrid 0.65 / ctx 1','reference':'Projected input'}[key]
                        d.text((x+8,y+8),short,font=font,fill='white')
                        d.text((x+8,y+28),'Wall details' if ri==0 else 'Desk and chair details',font=font,fill='#a8b9cb')
                detail.save(out/f'details_{idx:03d}.jpg',quality=97)
            if idx%80==0:print('Overview frame',idx,flush=True)
    for reader in readers.values():
        assert not reader.read()[0];reader.release()
    summary['region_temporal']={}
    for key,values in region_rows.items():
        result={}
        for field in ('known_temporal_mae','novel_temporal_mae'):
            valid=[r[field] for r in values if r[field] is not None]
            result[field]=dict(mean=float(np.mean(valid)),median=float(np.median(valid)),count=len(valid))
        summary['region_temporal'][key]=result
        row=next(r for r in flat if r['variant']==key)
        row.update({field:value['mean'] for field,value in result.items()})
    summary['region_method']='Motion-compensated luma MAE separately inside original FOV and outside it, eroded with 15x15 kernel; exclude novel regions with fewer than 128 pixels. No ground truth for novel-region appearance; lower residual can reflect blur.'
    (out/'metrics.json').write_text(json.dumps(summary,indent=2))
    (out/'region_temporal_per_frame.json').write_text(json.dumps(region_rows,indent=2))
    with (out/'metrics.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(4,1,figsize=(12,12),sharex=True)
    fields=['known_psnr_db','known_luma_ssim','motion_compensated_luma_mae_255']
    for key,values in rows.items():
        for ax,field in zip(axes,fields):
            ax.plot([r['time_seconds'] for r in values[1:]],[r[field] for r in values[1:]],label=labels[key],linewidth=1.1,alpha=.85)
    for key,values in region_rows.items():
        axes[3].plot([r['time_seconds'] for r in values],[r['novel_temporal_mae'] if r['novel_temporal_mae'] is not None else np.nan for r in values],label=labels[key],linewidth=1.1,alpha=.85)
    for ax,label in zip(axes,['Observed-region PSNR (dB)','Observed-region SSIM','Motion-compensated luma MAE','Novel-region temporal MAE']):
        ax.set_ylabel(label);ax.grid(alpha=.2)
        for frame in (80,160,240):ax.axvline(frame/30,color='gray',linestyle='--',alpha=.3)
    axes[0].legend(fontsize=8,ncol=2);axes[-1].set_xlabel('Time (s)')
    fig.tight_layout();fig.savefig(out/'metric_curves.png',dpi=160);plt.close(fig)
    print(json.dumps(flat,indent=2))


if __name__=='__main__':main()
