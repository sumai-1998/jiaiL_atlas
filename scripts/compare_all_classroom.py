#!/usr/bin/env python3
"""Combine all eight completed classroom variants and existing comparable metrics."""
import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from compare_worldwarp_hybrid import rotation_homography

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT/'WorldWarp_outputs'
OLD = OUTPUTS/'classroom_hybrid_tuning_2026-09-08'
NEW = OUTPUTS/'classroom_worldwarp_mapanything_2026-09-08'
SOURCES = [
    ('A','WorldWarp 原版',OUTPUTS/'classroom_pan_left_2026-09-07','old','original'),
    ('B','三项目初版',OUTPUTS/'classroom_hybrid_pan_left_2026-09-07/video','old','hybrid_previous'),
    ('C','三项目：上下文 5',OLD/'context_5','old','context_5'),
    ('D','三项目：strength 0.50',OLD/'strength_050','old','strength_050'),
    ('E','三项目：strength 0.65',OLD/'strength_065','old','strength_065'),
    ('F','两项目：滚动几何 + GS',NEW/'rolling_gs','new','rolling_gs'),
    ('G','两项目：原图约束 + GS',NEW/'anchor_gs','new','anchor_gs'),
    ('H','两项目：原图约束 + 点云',NEW/'anchor_points','new','anchor_points'),
]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    cv2.setNumThreads(4)
    summaries={'old':json.loads((OLD/'overview/metrics.json').read_text()),
               'new':json.loads((NEW/'comparison/comparison.json').read_text())}
    # The shared original and context-5 baselines independently produced the
    # same metrics in both previous evaluations. Reuse results without another
    # expensive full metric pass or changing the scoring definitions.
    for before,after in [('original','original'),('context_5','previous_best')]:
        for field in summaries['old']['metrics'][before]:
            np.testing.assert_allclose(summaries['old']['metrics'][before][field]['mean'],
                                       summaries['new']['metrics'][after][field]['mean'],atol=1e-12,rtol=0)
    base=SOURCES[0][2]
    reference=np.array(Image.open(base/'input_prepared.png').convert('RGB'))
    trajectory=np.load(base/'requested_camera_trajectory.npz')
    poses,ks=trajectory['c2w'],trajectory['intrinsics']
    br=json.loads((base/'report.json').read_text())
    artifact=Path(br['completed_chunks'][0]['path']).parent.parent
    captions=[(artifact/'captions'/f'chunk_{i:03d}.txt').read_bytes() for i in range(4)]
    versions={};flat=[]
    for letter,label,directory,group,key in SOURCES:
        r=json.loads((directory/'report.json').read_text())
        assert r['status']=='complete' and r['written_frames']==321 and r['fps']==30
        assert r['seed']==32 and r['prepared_size']==[480,608]
        np.testing.assert_array_equal(np.array(Image.open(directory/'input_prepared.png')),reference)
        traj=np.load(directory/'requested_camera_trajectory.npz')
        for field in ('c2w','intrinsics','fps'):
            np.testing.assert_array_equal(traj[field],trajectory[field])
        artifact=Path(r['completed_chunks'][0]['path']).parent.parent
        assert all((artifact/'captions'/f'chunk_{i:03d}.txt').read_bytes()==captions[i] for i in range(4))
        source=summaries[group]
        metrics=dict(source['metrics'][key])
        if group=='old':
            metrics.update(source['region_temporal'][key])
        row=dict(id=letter,label=label,strength=r['strength'],context=r.get('context_frames_2nd',1),
            psnr=metrics['known_psnr_db']['mean'],ssim=metrics['known_luma_ssim']['mean'],
            temporal_mae=metrics['motion_compensated_luma_mae_255']['mean'],
            novel_temporal_mae=metrics['novel_temporal_mae']['mean'],
            last_join_mae=source['joins'][key][-1]['motion_compensated_luma_mae_255'])
        flat.append(row)
        versions[letter]=dict(**row,directory=str(directory),video=r['output_video'],
            video_sha256=hashlib.sha256(Path(r['output_video']).read_bytes()).hexdigest(),
            metrics=metrics,chunks=source['chunks'][key],joins=source['joins'][key],
            metrics_source=str(OLD/'overview/metrics.json' if group=='old' else NEW/'comparison/comparison.json'))
    (out/'metrics.json').write_text(json.dumps(versions,indent=2,ensure_ascii=False))
    with (out/'metrics.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    (out/'validation.json').write_text(json.dumps(dict(input_pixels_equal=True,
        trajectories_equal=True,captions_equal=True,seed_equal=True,frames=321,fps=30,
        duplicated_baseline_metrics_equal=True,
        caveats=['Strength and context vary as explicitly labeled.','Geometry estimation, rendering, visibility masks and history updates differ between pipeline families.','One input image, one seed and pure rotation.','Known-region fidelity has no ground truth for unseen areas; low temporal residual may also reflect blur.']),indent=2))
    font=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc',18)
    readers={letter:cv2.VideoCapture(v['video']) for letter,v in versions.items()}
    for cap in readers.values():
        assert cap.isOpened() and cap.get(cv2.CAP_PROP_FPS)==30
    selected={0,40,80,81,120,160,161,200,240,241,280,320}
    grid=out/'classroom_all_8_versions_grid_10.7s.mp4'
    with imageio.get_writer(grid,fps=30,codec='libx264',quality=9,macro_block_size=1,
            ffmpeg_params=['-threads','8','-movflags','+faststart']) as writer:
        for idx in range(321):
            frames={}
            for letter,cap in readers.items():
                ok,bgr=cap.read();assert ok,f'{letter}: missing frame {idx}'
                rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);assert rgb.shape==(608,480,3)
                frames[letter]=rgb
            hom=rotation_homography(poses[0],poses[idx],ks[0],ks[idx])
            projected=cv2.warpPerspective(reference,hom,(480,608),flags=cv2.INTER_LINEAR)
            frames['I']=projected
            panel=Image.new('RGB',(1440,2016),'#171c24');draw=ImageDraw.Draw(panel)
            for cell,(letter,rgb) in enumerate(frames.items()):
                x,y=cell%3*480,cell//3*672
                panel.paste(Image.fromarray(rgb),(x,y+64))
                if letter=='I':
                    title='I  原图随相机投影（参考）';detail='黑色区域：原图没有观测到'
                else:
                    v=versions[letter];title=f'{letter}  {v["label"]}'
                    detail=f'{idx/30:5.2f}s  strength {v["strength"]:.2f}  上下文 {v["context"]}'
                draw.text((x+10,y+7),title,font=font,fill='white')
                draw.text((x+10,y+34),detail,font=font,fill='#b6c4d5')
            writer.append_data(np.asarray(panel))
            if idx in selected:
                panel.save(out/f'frame_{idx:03d}.jpg',quality=96)
            if idx in (160,240,320):
                for region,box,size in [('wall',(240,115,480,235),(320,160)),
                                        ('furniture',(220,350,480,608),(320,320)),
                                        ('new_area',(0,150,200,500),(240,420))]:
                    cw,ch=size;detail=Image.new('RGB',(cw*3,(ch+40)*3),'#171c24');dd=ImageDraw.Draw(detail)
                    for cell,(letter,rgb) in enumerate(frames.items()):
                        x,y=cell%3*cw,cell//3*(ch+40)
                        crop=ImageOps.contain(Image.fromarray(rgb).crop(box),size,Image.Resampling.LANCZOS)
                        detail.paste(crop,(x+(cw-crop.width)//2,y+40))
                        dd.text((x+8,y+8),letter,font=font,fill='white')
                    detail.save(out/f'{region}_{idx:03d}.jpg',quality=97)
            if idx%80==0:print(f'Tiled {idx}/320 frames',flush=True)
    for cap in readers.values():
        assert not cap.read()[0],'Unexpected extra frames'
        cap.release()
    probe=subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_entries',
        'stream=codec_name,width,height,r_frame_rate,nb_read_frames:format=duration,size','-of','json',str(grid)],text=True)
    info=json.loads(probe);stream=info['streams'][0]
    assert int(stream['nb_read_frames'])==321 and stream['r_frame_rate']=='30/1'
    assert (stream['width'],stream['height'])==(1440,2016) and abs(float(info['format']['duration'])-10.7)<1e-6
    (out/'ffprobe.json').write_text(probe)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='DejaVu Sans'
    fig,axes=plt.subplots(1,3,figsize=(12,5))
    colors=['#8e9aaf']*5+['#41a6b6','#267b8c','#8064a2']
    for ax,field,title in zip(axes,['psnr','ssim','temporal_mae'],['Known-region PSNR (higher better)','Known-region SSIM (higher better)','Temporal MAE (lower better)']):
        ax.barh([v['id'] for v in flat],[v[field] for v in flat],color=colors)
        ax.invert_yaxis();ax.set_title(title,fontsize=10);ax.grid(axis='x',alpha=.2)
        for i,row in enumerate(flat):ax.text(row[field],i,f'  {row[field]:.3f}',va='center',fontsize=9)
        ax.set_xlim(0,max(v[field] for v in flat)*1.2)
    fig.suptitle('All 8 classroom variants — fidelity and temporal residual are different criteria',fontsize=12)
    fig.tight_layout();fig.savefig(out/'metrics_overview.png',dpi=160);plt.close(fig)
    report=dict(status='complete',output_video=str(grid),versions=8,layout='3x3: eight videos plus rotation-projected input',
        frames=321,fps=30,duration_seconds=10.7,width=1440,height=2016,video_size_bytes=int(info['format']['size']),
        source_ids=list(versions),metric_computation='Existing final-video measurements reused after exact duplicate-baseline agreement and source compatibility checks.')
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(json.dumps(flat,indent=2,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
