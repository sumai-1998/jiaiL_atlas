#!/usr/bin/env python3
"""Evaluate the new combinations and create a synchronous classroom grid."""
import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from compare_worldwarp_hybrid import (aggregate, feature_motion, gray, reference_scores,
                                     rotation_homography, warp_and_mask)

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    args = p.parse_args()
    root = args.root.resolve()
    output = root/'comparison'
    output.mkdir(exist_ok=False)
    cv2.setNumThreads(4)
    dirs = dict(rolling_gs=root/'rolling_gs', anchor_gs=root/'anchor_gs',
                anchor_points=root/'anchor_points',
                original=ROOT/'WorldWarp_outputs/classroom_pan_left_2026-09-07',
                previous_best=ROOT/'WorldWarp_outputs/classroom_hybrid_tuning_2026-09-08/context_5')
    labels = dict(rolling_gs='滚动几何 + 原生 3DGS', anchor_gs='原图约束 + 原生 3DGS',
                  anchor_points='原图约束 + 点云投影', original='WorldWarp 原版（之前）',
                  previous_best='含 GaME 旧最佳（上下文 5）')
    short = dict(rolling_gs='Rolling GS', anchor_gs='Anchor GS', anchor_points='Anchor points',
                 original='WorldWarp original', previous_best='Previous GaME / ctx 5')
    reports = {key:json.loads((d/'report.json').read_text()) for key,d in dirs.items()}
    reference = np.array(Image.open(dirs['original']/'input_prepared.png').convert('RGB'))
    traj = np.load(dirs['original']/'requested_camera_trajectory.npz')
    poses, ks, fps = traj['c2w'], traj['intrinsics'], int(traj['fps'])
    h, w = reference.shape[:2]
    baseline_artifact = Path(reports['original']['completed_chunks'][0]['path']).parent.parent
    baseline_captions = [(baseline_artifact/'captions'/f'chunk_{i:03d}.txt').read_bytes() for i in range(4)]
    checks = {}
    for key, directory in dirs.items():
        report = reports[key]
        assert report['status']=='complete' and report['written_frames']==321 and report['fps']==30
        assert report['seed']==32 and report['strength']==.6
        np.testing.assert_array_equal(np.array(Image.open(directory/'input_prepared.png')), reference)
        t = np.load(directory/'requested_camera_trajectory.npz')
        for field in ('c2w', 'intrinsics', 'fps'):
            np.testing.assert_array_equal(t[field], traj[field])
        artifact = Path(report['completed_chunks'][0]['path']).parent.parent
        for i in range(4):
            assert (artifact/'captions'/f'chunk_{i:03d}.txt').read_bytes()==baseline_captions[i]
        checks[key] = dict(input_equal=True, trajectory_equal=True, captions_equal=True,
                          context=report.get('context_frames_2nd',1), strength=report['strength'])
        if key in ('rolling_gs','anchor_gs','anchor_points'):
            pipeline = json.loads((directory/'pipeline_report.json').read_text())
            assert pipeline['game_used'] is False and pipeline['ttt3r_model_loaded'] is False
            assert pipeline['geometry_updates_from_generated_frames'] is True
            for i, call in enumerate(pipeline['calls']):
                assert call['chunk']==i
                assert call['exported_target_frames']==[i*80,i*80+80]
                assert max(call['source_global_frames'])<=i*80
                if i:
                    assert not all(call['source_observed'])
                    # Verify every fed generated image against the actual previous
                    # chunk file, not only its claimed global frame index.
                    source = np.load(directory/'geometry'/f'chunk_{i:03d}'/'mapanything_input.npz')
                    cap = cv2.VideoCapture(report['completed_chunks'][i-1]['path'])
                    for j,(global_id, observed) in enumerate(zip(source['frame_ids'],source['observed'])):
                        if observed:
                            np.testing.assert_array_equal(source['rgb'][j],reference)
                        else:
                            cap.set(cv2.CAP_PROP_POS_FRAMES,int(global_id-(i-1)*80))
                            ok, frame = cap.read(); assert ok
                            np.testing.assert_array_equal(source['rgb'][j],cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
                    cap.release()
            checks[key]['generated_history_pixels_verified'] = True
    (output/'config_checks.json').write_text(json.dumps(checks,indent=2))
    readers = {key:cv2.VideoCapture(r['output_video']) for key,r in reports.items()}
    rows, previous = {key:[] for key in readers}, {}
    font = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc',18)
    selected = {0,40,80,81,120,160,161,200,240,241,280,320}
    grid_path = output/'classroom_worldwarp_mapanything_grid_10.7s.mp4'
    with imageio.get_writer(grid_path,fps=fps,codec='libx264',quality=9,macro_block_size=1,
                           ffmpeg_params=['-threads','8','-movflags','+faststart']) as writer:
        for idx in range(321):
            frames = {}
            hom = rotation_homography(poses[0],poses[idx],ks[0],ks[idx])
            projected, known = warp_and_mask(reference,hom,(w,h))
            raw_support = cv2.warpPerspective(np.ones((h,w),np.uint8),hom,(w,h),flags=cv2.INTER_NEAREST)
            novel = cv2.erode(1-raw_support,np.ones((15,15),np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0).astype(bool)
            relative = rotation_homography(poses[idx-1],poses[idx],ks[idx-1],ks[idx]) if idx else None
            for key,reader in readers.items():
                ok,bgr = reader.read(); assert ok
                rgb = cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
                assert rgb.shape==reference.shape
                frames[key] = rgb
                row = dict(frame=idx,time_seconds=idx/fps,known_fraction=float(known.mean()),
                           **reference_scores(rgb,projected,known))
                if idx:
                    warped, overlap = warp_and_mask(previous[key],relative,(w,h))
                    residual = np.abs(gray(rgb)-gray(warped))
                    row['motion_compensated_luma_mae_255'] = float(residual[overlap].mean())
                    row['known_temporal_mae'] = float(residual[overlap & known].mean())
                    if (overlap & novel).sum()>=128:
                        row['novel_temporal_mae'] = float(residual[overlap & novel].mean())
                    row.update(feature_motion(previous[key],rgb,relative))
                rows[key].append(row)
            panel = Image.new('RGB',(w*3,(h+64)*2),'#171c24')
            draw = ImageDraw.Draw(panel)
            for cell,(key,rgb) in enumerate(list(frames.items())+[('reference',reference)]):
                x,y=(cell%3)*w,(cell//3)*(h+64)
                panel.paste(Image.fromarray(rgb),(x,y+64))
                title = labels.get(key,'输入图片（静态参考）')
                draw.text((x+10,y+7),title,font=font,fill='white')
                subtitle = '其余 5 格按同一时间同步播放' if key=='reference' else f'{idx/fps:5.2f}s  左转 {idx/16:5.2f}°  上下文 {reports[key].get("context_frames_2nd",1)}'
                draw.text((x+10,y+34),subtitle,font=font,fill='#b6c4d5')
            writer.append_data(np.asarray(panel))
            if idx in selected:
                panel.save(output/f'frame_{idx:03d}.jpg',quality=96)
            if idx in (160,240,320):
                # Identical target-image crops compare visible details and the
                # newly exposed region, with a projected known-region reference.
                boxes=[(240,115,480,235),(220,350,480,608),(0,150,200,500)]
                detail=Image.new('RGB',(6*300,3*320),'#171c24');dd=ImageDraw.Draw(detail)
                for col,(key,rgb) in enumerate(list(frames.items())+[('reference',projected)]):
                    for ri,box in enumerate(boxes):
                        from PIL import ImageOps
                        crop=ImageOps.contain(Image.fromarray(rgb).crop(box),(300,280),Image.Resampling.LANCZOS)
                        x,y=col*300,ri*320
                        detail.paste(crop,(x+(300-crop.width)//2,y+40))
                        dd.text((x+8,y+8),short.get(key,'Projected input'),font=font,fill='white')
                detail.save(output/f'details_{idx:03d}.jpg',quality=97)
            previous=frames
            if idx%80==0:
                print(f'Compared and tiled {idx}/320 frames',flush=True)
    for reader in readers.values():
        assert not reader.read()[0]
        reader.release()
    metrics={key:aggregate(value[1:]) for key,value in rows.items()}
    for key,value in rows.items():
        for field in ('known_temporal_mae','novel_temporal_mae'):
            values=[r[field] for r in value[1:] if field in r]
            metrics[key][field]=dict(mean=float(np.mean(values)),median=float(np.median(values)),count=len(values))
    summary=dict(status='complete',labels=labels,videos={key:r['output_video'] for key,r in reports.items()},
        grid_video=str(grid_path),grid_layout='3 columns x 2 rows; simultaneous playback; five videos plus static input',
        frames=321,fps=30,duration_seconds=10.7,metrics=metrics,
        joins={key:[value[i] for i in (81,161,241)] for key,value in rows.items()},
        chunks={key:[dict(chunk=i+1,**aggregate([r for r in value if i*80<r['frame']<=(i+1)*80])) for i in range(4)] for key,value in rows.items()},
        config_checks=checks,
        method=dict(known_region='Original input projected by exact fixed-center rotation; 15x15 erosion; frame 0 excluded.',
            temporal='Motion-compensated luma MAE over overlap, plus known/novel regions separately. Lower residual can also mean blur.',
            interpretation='One image, one seed, pure rotation. No ground truth for newly revealed areas. Original WorldWarp uses context 1; all other grid videos use context 5.',
            geometry='Three new variants all use fresh MapAnything estimates of previous generated history; no GaME or TTT3R inference. GS variants use native WorldWarp fitting/rasterization and exact rotation visibility.'))
    probe=subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_entries',
        'stream=codec_name,width,height,r_frame_rate,nb_read_frames:format=duration,size','-of','json',str(grid_path)],text=True)
    info=json.loads(probe);stream=info['streams'][0]
    assert int(stream['nb_read_frames'])==321 and stream['r_frame_rate']=='30/1'
    assert (stream['width'],stream['height'])==(1440,1344)
    assert abs(float(info['format']['duration'])-10.7)<1e-6
    (output/'ffprobe.json').write_text(probe)
    (output/'comparison.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    (output/'per_frame.json').write_text(json.dumps(rows,indent=2))
    flat=[]
    for key,value in metrics.items():
        flat.append(dict(variant=key,label=labels[key],**{field:result['mean'] for field,result in value.items()}))
    with (output/'metrics.csv').open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(4,1,figsize=(12,12),sharex=True)
    fields=['known_psnr_db','known_luma_ssim','motion_compensated_luma_mae_255','novel_temporal_mae']
    for key,value in rows.items():
        for ax,field in zip(axes,fields):
            ax.plot([r['time_seconds'] for r in value[1:]],[r.get(field,np.nan) for r in value[1:]],label=short[key],linewidth=1.1)
    for ax,label in zip(axes,['Known-region PSNR (dB)','Known-region SSIM','Motion-compensated MAE','Novel-region temporal MAE']):
        ax.set_ylabel(label);ax.grid(alpha=.2)
        for frame in (80,160,240):ax.axvline(frame/30,color='gray',linestyle='--',alpha=.3)
    axes[0].legend(fontsize=8,ncol=2);axes[-1].set_xlabel('Time (s)')
    fig.tight_layout();fig.savefig(output/'metric_curves.png',dpi=160);plt.close(fig)
    print(json.dumps(flat,indent=2,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
