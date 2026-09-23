"""Verify F/G/H, export a compact self-contained comparison, then prune own intermediates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image, ImageDraw

from worldwarp_benchmark import dump
from worldwarp_hybrid_benchmark import sha256
from worldwarp_rolling_benchmark import select_sources
from worldwarp_benchmark_metrics import frechet_low_rank
from compare_dl3dv_benchmarks import LABELS, METRICS, aggregate_baseline, html


def probe(path, width, height):
    data=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames,r_frame_rate,width,height,duration','-of','json',str(path)]))['streams'][0]
    assert (int(data['nb_read_frames']),data['r_frame_rate'],data['width'],data['height'])==(225,'30/1',width,height)
    assert abs(float(data['duration'])-7.5)<1e-6
    return data


def verify_run(out):
    plan=json.loads((out/'plan.json').read_text());status=json.loads((out/'status.json').read_text())
    summary=json.loads((out/'metrics_summary.json').read_text());method=plan['method']
    assert status['status']==summary['status']=='complete'
    assert method in ('map-ww-gs','map-ww-anchor-gs','map-ww-anchor-points')
    assert len(plan['inputs'])==summary['scene_count']==5
    pngs=0;rows=0;features=[];scene_reports=[]
    for entry in plan['inputs']:
        folder=out/entry['scene_id'][:12];base=Path(entry['baseline_scene_dir'])
        provenance=json.loads((folder/'paired_input_provenance.json').read_text())
        assert not provenance['reference_depth_copied'] and not provenance['baseline_generated_images_copied']
        for relative,digest in provenance['sha256'].items():
            assert sha256(folder/relative)==sha256(base/relative)==digest
        for kind in ('gt','generated'):
            files=sorted((folder/kind).glob('*.png'));assert [p.name for p in files]==[f'{i:05d}.png' for i in range(225)]
            for p in files:
                with Image.open(p) as im:assert im.size==(720,480);im.verify()
            pngs+=len(files)
        image=json.loads((folder/'image_metrics.json').read_text());pose=json.loads((folder/'pose_metrics.json').read_text())
        gen=json.loads((folder/'generation/report.json').read_text())
        assert image['status']==pose['status']==gen['status']=='complete'
        assert [r['index'] for r in image['frames']]==list(range(225));rows+=225
        assert gen['method']==method and gen['frames']==225 and len(gen['chunks'])==5
        assert not gen['game_used'] and not gen['ttt3r_model_loaded_in_generator']
        calls=gen['geometry_bridge_calls'];assert len(calls)==5
        first_hash=hashlib.sha256(np.array(Image.open(folder/'gt/00000.png')).tobytes()).hexdigest()
        calibration=json.loads((folder/'geometry/scale_calibration.json').read_text())
        assert calibration['scale']>0 and not calibration['held_out_depth_used']
        for i,call in enumerate(calls):
            selected=select_sources(i,method!='map-ww-gs')
            assert call['source_global_frames']==[r[0] for r in selected]
            assert call['source_observed']==[r[1] for r in selected]
            assert call['global_target_indices']==list(range(i*44,i*44+49))
            assert call['context_global_indices']==list(range(i*44,i*44+(1 if i==0 else 5)))
            assert call['scale']==calibration['scale']
            expected=[first_hash if observed else gen['chunks'][i-1]['decoded_frame_sha256'][local]
                      for _,observed,local in selected]
            assert call['source_image_sha256']==expected
            assert not call['worldwarp_ttt3r_geometry_inference'] and not call['game_used']
            assert call['backend']==('points' if method.endswith('points') else 'gs')
            expected_weights=[1] if len(selected)==1 else [2 if r[1] else 1 for r in selected]
            assert call['render_report']['source_weights']==expected_weights
            if call['backend']=='gs':assert call['render_report']['iterations']==500
            assert len(call['render_report']['valid_fraction_per_frame'])==49
            for removed in call['compact_removed_after_render']:
                assert not (folder/'generation/geometry'/f'chunk_{i:03d}'/removed['file']).exists()
        # Pre-encoding generated frames exactly match the retained output hashes (not the MP4).
        for i,p in enumerate(sorted((folder/'generated').glob('*.png'))):
            chunk=0 if i<49 else (i-49)//44+1;local=i-chunk*44
            assert hashlib.sha256(np.array(Image.open(p)).tobytes()).hexdigest()==gen['chunks'][chunk]['decoded_frame_sha256'][local]
        videos={name:probe(folder/name,width,480) for name,width in
                [('generated.mp4',720),('ground_truth.mp4',720),('comparison.mp4',1440)]}
        feat=dict(np.load(folder/'inception_features.npz'));features.append(feat)
        np.testing.assert_allclose(feat['gt'],np.load(base/'inception_features.npz')['gt'],atol=1e-5,rtol=1e-5)
        scene_reports.append(dict(scene_id=entry['scene_id'],videos=videos))
    for endpoint in ('50','200'):
        for key in METRICS:
            vals=[s['image'][endpoint][key] if key in ('psnr_db','ssim','lpips') else s['pose'][endpoint][key]
                  for s in summary['scenes']]
            np.testing.assert_allclose(summary['endpoints'][endpoint][key],np.mean(vals),rtol=1e-12,atol=1e-12)
        fid=frechet_low_rank(np.stack([f['gt'][int(endpoint)-1] for f in features]),
                            np.stack([f['generated'][int(endpoint)-1] for f in features]))
        np.testing.assert_allclose(summary['endpoints'][endpoint]['FID_endpoint_diagnostic'],fid,atol=1e-7)
    timing=dict(total_seconds=status['finished_unix']-status['started_unix'],
        started_local=datetime.fromtimestamp(status['started_unix'],ZoneInfo('Asia/Shanghai')).isoformat(),
        finished_local=datetime.fromtimestamp(status['finished_unix'],ZoneInfo('Asia/Shanghai')).isoformat(),stage_seconds={})
    for s in status['steps']:
        k=s['name'].split('_',1)[-1];timing['stage_seconds'][k]=timing['stage_seconds'].get(k,0)+s['finished_unix']-s['started_unix']
    dump(out/'timing_summary.json',timing)
    result=dict(status='passed',scene_count=5,lossless_pngs=pngs,image_metric_rows=rows,
        paired_hashes_match=True,actual_geometry_and_history_hashes_checked=True,
        lossless_generation_hashes_checked=True,aggregate_means_and_endpoint_FID_checked=True,scenes=scene_reports)
    dump(out/'verification.json',result)
    print('Verified',method,flush=True)
    return plan,summary


def link(src,dst):
    """Self-contained regular file via hardlink when possible; no symlinks."""
    dst.parent.mkdir(parents=True,exist_ok=True)
    try:os.link(src,dst)
    except OSError:shutil.copy2(src,dst)


def prune_run(out,report):
    plan=json.loads((out/'plan.json').read_text())
    assert plan['method'].startswith('map-ww-') and plan['parameters']['retention'].startswith('compact:')
    assert json.loads((out/'verification.json').read_text())['status']=='passed'
    assert json.loads((report/'export_verification.json').read_text())['status']=='passed'
    removed=[];geometry_removed=0
    def delete(path):
        if not path.exists():return
        assert not path.is_symlink() and path.resolve().is_relative_to(out.resolve())
        files=list(path.rglob('*')) if path.is_dir() else [path]
        for f in files:
            if f.is_file():removed.append(dict(file=str(f.relative_to(out)),bytes=f.stat().st_size))
        if path.is_dir():shutil.rmtree(path)
        else:path.unlink()
    for e in plan['inputs']:
        folder=out/e['scene_id'][:12]
        generation=json.loads((folder/'generation/report.json').read_text())
        geometry_removed+=sum(r['bytes'] for call in generation['geometry_bridge_calls'] for r in call['compact_removed_after_render'])
        shutil.copy2(folder/'gt/00000.png',folder/'input.png')
        # Retain only caption text from the large native artifacts tree.
        for f in (folder/'generation/artifacts').rglob('captions/*.txt'):
            dst=folder/'generation/captions'/f.name;dst.parent.mkdir(exist_ok=True);shutil.copy2(f,dst)
        for name in ('gt','generated','generation/artifacts','generation/initial_image_repeated.mp4',
                     'mapanything/pointmaps.npz','mapanything/raw_prediction.npz','mapanything/posed_rgbd.npz',
                     'geometry/posed_rgbd.npz','geometry/first_image_ttt3r_scale_reference.npz',
                     'comparison.mp4','ground_truth.mp4'):
            delete(folder/name)
    delete(out/'all_scenes_comparison.mp4')
    dump(out/'retention_manifest.json',dict(status='complete',policy='User requested necessary videos/metrics only',
        verification_before_deletion=True,deleted=removed,deleted_file_bytes=sum(r['bytes'] for r in removed),
        geometry_bytes_removed_during_generation=geometry_removed,scoring='Lossless PNG before encoding, already verified',
        limitation='Exact image-metric recomputation requires regeneration; retained MP4 is lossy',report=str(report)))
    md=f'# {plan["method_label"]}：已完成并精简保存\n\n'+f'[完整对照报告]({os.path.relpath(report/"README.md",out)})\n\n'
    md+='保留成片、六项指标 / 逐帧 CSV、FID 特征、相机、caption、配置、日志、来源哈希和核验记录。逐帧 PNG、GS 模型及大型几何已在使用和评分完成后删除；详情见 retention_manifest.json。视频有损，不能代替原 PNG 精确复算图像指标。\n\n'
    for e in plan['inputs']:
        f=e['scene_id'][:12];md+=f'- {LABELS[f]}：[成片]({f}/generated.mp4)，[逐帧指标]({f}/image_metrics.csv)。\n'
    (out/'README.md').write_text(md);(out/'index.html').write_text(html(md))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',nargs=3,type=Path,required=True)
    p.add_argument('--hybrid-run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prune',action='store_true')
    a=p.parse_args();dest=a.output.resolve();runs=[x.resolve() for x in a.runs]
    if dest.exists():raise FileExistsError(dest)
    plans=[];summaries={};methods={}
    for label,out in zip('FGH',runs):
        plan,summary=verify_run(out)
        assert plan['method']==dict(F='map-ww-gs',G='map-ww-anchor-gs',H='map-ww-anchor-points')[label]
        plans.append(plan);summaries[label]=summary;methods[label]=out
    ids=[s['scene_id'] for s in plans[0]['inputs']]
    assert all([s['scene_id'] for s in plan['inputs']]==ids for plan in plans)
    hybrid=json.loads((a.hybrid_run/'metrics_summary.json').read_text())
    assert hybrid['status']=='complete' and [s['scene_id'] for s in hybrid['scenes']]==ids
    records=[]
    for e in plans[0]['inputs']:
        base=Path(e['baseline_scene_dir'])
        records.append(dict(scene_id=e['scene_id'],base=base,
            image=json.loads((base/'image_metrics.json').read_text()),pose=json.loads((base/'pose_metrics.json').read_text())))
    baseline=aggregate_baseline(records);summaries={'WorldWarp':baseline,'GaME':hybrid,**summaries}
    comparison=dict(scene_ids=ids,methods={k:v['endpoints'] for k,v in summaries.items()},improved_scene_counts={},
        caveats=['Five scenes / one seed; endpoint FID diagnostic only','TTT3R first-image scale calibration also used by F/G/H',
                 'Qwen follows own history; whole-pipeline comparison, not one-variable ablation'])
    states=[json.loads((out/'status.json').read_text()) for out in runs]
    comparison['parallel_batch_wall_seconds']=max(s['finished_unix'] for s in states)-min(s['started_unix'] for s in states)
    for label in 'FGH':
        wins={ep:{m:0 for m in METRICS} for ep in ('50','200')}
        for old,new in zip(records,summaries[label]['scenes']):
            assert old['scene_id']==new['scene_id']
            for ep in wins:
                for m in METRICS:
                    x=(new['image'][ep] if m in ('psnr_db','ssim','lpips') else new['pose'][ep])[m]
                    y=(old['image']['endpoints'][ep] if m in ('psnr_db','ssim','lpips') else old['pose']['endpoints'][ep]['generated'])[m]
                    wins[ep][m]+=int(x>y if m in ('psnr_db','ssim') else x<y)
        comparison['improved_scene_counts'][label]=wins
    dest.mkdir(parents=True)
    dump(dest/'comparison_summary.json',comparison)
    for label,out in methods.items():
        for name in ('metrics_summary.json','verification.json','timing_summary.json','plan.json','status.json','environment_and_code.json'):
            link(out/name,dest/'metrics'/label/name)
    dump(dest/'baseline_five_scene_summary.json',baseline);dump(dest/'hybrid_metrics_summary.json',hybrid)
    import imageio.v2 as imageio
    lines=['# F/G/H：同五个 DL3DV 场景的配对评测','',
        'F：滚动历史 GS；G：原图约束 GS；H：原图约束点云。均为 MapAnything + WorldWarp，不使用 GaME。',
        '与之前原版 / 三项目对齐 225 帧、720×480、30 fps（7.5 秒）、5×49 帧 / 后续重叠 5、strength .8、采样 50、CFG 5、seed 32。完整 SE3 轨迹来自同一参考相机，图像 / 相机哈希一致。这是基准适配版，不是旧 classroom .6 纯旋转配置。','',
        '首图单独 TTT3R / MapAnything 深度比中位数校准一个全局尺度，后续窗口沿用，窗口尺度漂移未额外修正。F/G 每段拟合原生 GS 500 步，H 不优化 GS。几何关键帧取上一段 0/12/24/36/48，视频上下文取连续末尾 5 帧。G/H 原图权重 2；生成历史不是真实观测。Qwen 跟随各自历史，后续文本可能不同。','',
        '## 六项指标，五场景等权汇总','',
        '| 帧 | 方法 | PSNR ↑ | SSIM ↑ | LPIPS ↓ | R_dist ↓ rad | t_dist ↓ | FID ↓ 诊断 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for ep in ('50','200'):
        for name,data in summaries.items():
            m=data['endpoints'][ep]
            lines.append(f'| {ep} | {name} | {m["psnr_db"]:.3f} | {m["ssim"]:.4f} | {m["lpips"]:.4f} | {m["R_dist_rad"]:.4f} | {m["t_dist"]:.4f} | {m["FID_endpoint_diagnostic"]:.3f} |')
    lines+=['','FID 合并五场景特征计算，未平均批次 FID；每端点仅 5 张图，不能作为论文排名。平移误差不是时间或米，而是各自轨迹最大半径归一化后的 L2。DUSt3R 在退化画面上可能估计不可靠。','',
            '## 相比原版数值改善的场景数','',
            '| 帧 | 方法 | PSNR | SSIM | LPIPS | R_dist | t_dist |','|---|---|---:|---:|---:|---:|---:|']
    for ep in ('50','200'):
        for label in 'FGH':lines.append('| '+ep+' | '+label+' | '+' | '.join(str(comparison['improved_scene_counts'][label][ep][m])+'/5' for m in METRICS)+' |')
    video_probes=[]
    for entry,record in zip(plans[0]['inputs'],records):
        folder=entry['scene_id'][:12];target=dest/folder;target.mkdir()
        sources=[record['base']/'gt',record['base']/'generated',a.hybrid_run/folder/'generated']+[r/folder/'generated' for r in runs]
        names=['GT','WorldWarp','GaME','F','G','H']
        videos=[record['base']/'ground_truth.mp4',record['base']/'generated.mp4',a.hybrid_run/folder/'generated.mp4']+[r/folder/'generated.mp4' for r in runs]
        for name,video in zip(names,videos):link(video,target/(name+'.mp4'))
        with imageio.get_writer(target/'comparison.mp4',fps=30,codec='libx264',quality=8,macro_block_size=1,ffmpeg_params=['-threads','4']) as writer:
            for i in range(225):
                canvas=Image.new('RGB',(2160,960));draw=ImageDraw.Draw(canvas)
                for j,(source,name) in enumerate(zip(sources,names)):
                    x,y=(j%3)*720,(j//3)*480
                    with Image.open(source/f'{i:05d}.png') as im:canvas.paste(im,(x,y))
                    draw.rectangle((x,y,x+720,y+24),fill='black');draw.text((x+8,y+5),f'{name} | {folder} | frame {i+1}',fill='white')
                writer.append_data(np.asarray(canvas))
                if i in (49,199,224):canvas.save(target/f'frame_{i+1:03d}.jpg',quality=92)
        video_probes.append(dict(scene=folder,**probe(target/'comparison.mp4',2160,960)))
        for label,out in methods.items():
            for name in ('image_metrics.csv','image_metrics.json','pose_metrics.json','inception_features.npz',
                         'dataset_cameras.npz','reference_ttt3r_cameras.npz','paired_input_provenance.json',
                         'generation/report.json','geometry/scale_calibration.json'):
                link(out/folder/name,dest/'metrics'/label/folder/name)
        lines += ['',f'## {LABELS[folder]}','',f'[六格同步对比视频]({folder}/comparison.mp4)：上排 真实 / WorldWarp / 三项目，下排 F / G / H。','',
                  f'![第 50 帧]({folder}/frame_050.jpg)','',f'![第 200 帧]({folder}/frame_200.jpg)','',
                  '单独成片：'+' · '.join(f'[{n}]({folder}/{n}.mp4)' for n in names),'']
        lines+=['逐帧指标：'+' · '.join(f'[{label} CSV](metrics/{label}/{folder}/image_metrics.csv)' for label in 'FGH'),'',
                '| 帧 | 方法 | PSNR ↑ | SSIM ↑ | LPIPS ↓ | R_dist ↓ rad | t_dist ↓ |',
                '|---|---|---:|---:|---:|---:|---:|']
        for ep in ('50','200'):
            values=[('WorldWarp',{**record['image']['endpoints'][ep],**record['pose']['endpoints'][ep]['generated']})]
            for name in ('GaME','F','G','H'):
                s=next(x for x in summaries[name]['scenes'] if x['scene_id']==entry['scene_id'])
                values.append((name,{**s['image'][ep],**s['pose'][ep]}))
            for name,m in values:
                lines.append(f'| {ep} | {name} | {m["psnr_db"]:.3f} | {m["ssim"]:.4f} | {m["lpips"]:.4f} | {m["R_dist_rad"]:.4f} | {m["t_dist"]:.4f} |')
        print('Exported scene',folder,flush=True)
    lines+=['## 保存与复查','',
        '本目录自包含所引用的图片、视频及指标，可整体复制离线阅读。为节约空间不再另复制 ZIP；同一文件在本机通过硬链接复用，复制到其他设备后仍是普通完整文件，不依赖外部路径。',
        '指标从编码前无损 PNG 计算并核验；按用户要求，报告完成后清理本次 F/G/H 的全部逐帧 PNG、模型和大型几何，只保留成片、指标 / FID 特征、相机、配置、日志、哈希、caption 和少量预览。保留视频是有损编码，不能精确复算原无损像素指标；需要时重新生成。旧实验未清理。','',
        f'三条方法并行的正式运行跨度为 {comparison["parallel_batch_wall_seconds"]/60:.1f} 分钟。以下各方法耗时包括模型加载和指标，不含开发及最后对比导出：','']
    for label,out in methods.items():
        t=json.loads((out/'timing_summary.json').read_text());lines.append(f'- {label}：{t["total_seconds"]/60:.1f} 分钟，{t["started_local"]}—{t["finished_local"]}。')
    md='\n'.join(lines)+'\n';(dest/'README.md').write_text(md);(dest/'index.html').write_text(html(md))
    links=re.findall(r'\[[^\]]*\]\(([^)]+)\)',md)
    assert all((dest/p).exists() for p in links)
    dump(dest/'export_verification.json',dict(status='passed',links_checked=len(links),video_probes=video_probes,
         all_15_scene_metrics_verified=True,media_self_contained=True))
    if a.prune:
        for out in runs:prune_run(out,dest)
    print('Report complete:',dest,flush=True)


if __name__=='__main__':main()
