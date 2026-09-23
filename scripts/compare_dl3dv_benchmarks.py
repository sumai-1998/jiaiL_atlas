#!/usr/bin/env python3
"""Export a self-contained paired WorldWarp / MapAnything-GaME-WorldWarp report."""
import argparse
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

import numpy as np

from worldwarp_benchmark import dump
from worldwarp_benchmark_metrics import frechet_low_rank
from worldwarp_hybrid_benchmark import sha256


LABELS={'032dee9fb0a8':'建筑与雕像','0569e83fdc24':'温室花展','06da79666629':'餐厅',
        '3bb894d1933f':'室外街边商铺','adf35184a12d':'室内汽车展厅'}
METRICS=('psnr_db','ssim','lpips','R_dist_rad','t_dist')


def aggregate_baseline(records):
    endpoints={}
    features=[dict(np.load(r['base']/'inception_features.npz')) for r in records]
    for ep in ('50','200'):
        row={k:float(np.mean([r['image']['endpoints'][ep][k] for r in records]))
             for k in ('psnr_db','ssim','lpips')}
        row.update({k:float(np.mean([r['pose']['endpoints'][ep]['generated'][k] for r in records]))
                    for k in ('R_dist_rad','R_dist_deg','t_dist')})
        row['FID_endpoint_diagnostic']=frechet_low_rank(
            np.stack([f['gt'][int(ep)-1] for f in features]),
            np.stack([f['generated'][int(ep)-1] for f in features]))
        row['FID_sample_count']=len(records);endpoints[ep]=row
    return dict(status='complete',scene_count=len(records),method='worldwarp',
        scene_ids=[r['scene_id'] for r in records],endpoints=endpoints,
        FID_all_novel_frames_diagnostic=frechet_low_rank(
            np.concatenate([f['gt'][1:] for f in features]),
            np.concatenate([f['generated'][1:] for f in features])),
        note='Pooled cached features, not an average of batch FIDs; no baseline regeneration')


def html(md):
    import markdown
    body=markdown.markdown(md,extensions=['tables','fenced_code'])
    body=re.sub(r'<a href="([^"]+\.mp4)">([^<]+)</a>',
                r'<a href="\1">\2</a><video controls preload="metadata" src="\1"></video>',body)
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>DL3DV 五场景配对评测</title><style>'
            'body{max-width:1300px;margin:32px auto;padding:0 18px;font:16px/1.7 system-ui,sans-serif}'
            'img,video{max-width:100%;height:auto}video{display:block;margin:12px 0}'
            'table{border-collapse:collapse;display:block;overflow:auto}th,td{border:1px solid #ccc;padding:8px}'
            'pre{overflow:auto;background:#f5f5f5;padding:12px}a{color:#145da0}</style><body>'+body+'</body></html>')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hybrid-run',type=Path,required=True)
    parser.add_argument('--report-output',type=Path,required=True)
    args=parser.parse_args()
    out=args.hybrid_run.resolve();dest=args.report_output.resolve()
    if dest.exists():raise FileExistsError(dest)
    plan=json.loads((out/'plan.json').read_text())
    status=json.loads((out/'status.json').read_text())
    summary=json.loads((out/'metrics_summary.json').read_text())
    if status['status']!='complete' or summary.get('method')!='map-game-ww':
        raise ValueError('Expected completed hybrid benchmark')
    records=[]
    for entry in plan['inputs']:
        folder=entry['scene_id'][:12];base=Path(entry['baseline_scene_dir'])
        provenance=json.loads((out/folder/'paired_input_provenance.json').read_text())
        for relative,digest in provenance['sha256'].items():
            if sha256(base/relative)!=digest or sha256(out/folder/relative)!=digest:
                raise RuntimeError(f'Paired input changed: {folder}/{relative}')
        old_feature=np.load(base/'inception_features.npz')['gt']
        new_feature=np.load(out/folder/'inception_features.npz')['gt']
        np.testing.assert_allclose(new_feature,old_feature,atol=1e-5,rtol=1e-5)
        records.append(dict(scene_id=entry['scene_id'],folder=folder,base=base,
            image=json.loads((base/'image_metrics.json').read_text()),
            pose=json.loads((base/'pose_metrics.json').read_text())))
    baseline=aggregate_baseline(records)
    dump(out/'baseline_five_scene_summary.json',baseline)
    comparison=dict(scene_count=len(records),baseline=baseline['endpoints'],hybrid=summary['endpoints'],
        delta_hybrid_minus_baseline={ep:{m:summary['endpoints'][ep][m]-baseline['endpoints'][ep][m]
            for m in (*METRICS,'FID_endpoint_diagnostic')} for ep in ('50','200')},
        input_and_reference_camera_hashes_match=True,
        FID_note='Recomputed from pooled features; only five endpoint images, diagnostic only')
    by_scene={r['scene_id']:r for r in summary['scenes']}
    wins={ep:{m:0 for m in METRICS} for ep in ('50','200')}
    comparison['per_scene']={}
    for r in records:
        new=by_scene[r['scene_id']];endpoints={}
        for ep in ('50','200'):
            old_values={**r['image']['endpoints'][ep],**r['pose']['endpoints'][ep]['generated']}
            new_values={**new['image'][ep],**new['pose'][ep]}
            delta={m:new_values[m]-old_values[m] for m in METRICS}
            for m in METRICS:
                wins[ep][m]+=int(delta[m]>0 if m in ('psnr_db','ssim') else delta[m]<0)
            endpoints[ep]=dict(baseline={m:old_values[m] for m in METRICS},
                               hybrid={m:new_values[m] for m in METRICS},delta_hybrid_minus_baseline=delta)
        comparison['per_scene'][r['folder']]=endpoints
    comparison['improved_scene_counts']=wins
    dump(out/'paired_comparison_summary.json',comparison)
    import imageio.v2 as imageio
    from PIL import Image,ImageDraw
    # Decode PNG, not already compressed comparison videos.
    combined=out/'paired_all_scenes_comparison.mp4'
    writers=[imageio.get_writer(out/r['folder']/'paired_comparison.mp4',fps=30,codec='libx264',quality=9,macro_block_size=1,ffmpeg_params=['-threads','2'])
             for r in records]
    with imageio.get_writer(combined,fps=30,codec='libx264',quality=9,macro_block_size=1,ffmpeg_params=['-threads','2']) as whole:
        try:
            for i in range(225):
                rows=[]
                for r,writer in zip(records,writers):
                    folder=out/r['folder']
                    paths=[folder/'gt'/f'{i:05d}.png',r['base']/'generated'/f'{i:05d}.png',folder/'generated'/f'{i:05d}.png']
                    canvas=Image.new('RGB',(2160,480))
                    for column,(path,label) in enumerate(zip(paths,['Ground truth','WorldWarp baseline','MapAnything + GaME + WorldWarp'])):
                        with Image.open(path) as im:canvas.paste(im,(720*column,0))
                        draw=ImageDraw.Draw(canvas);draw.rectangle((720*column,0,720*(column+1),24),fill='black')
                        draw.text((720*column+8,5),f'{label} | {r["folder"]} | frame {i+1}',fill='white')
                    writer.append_data(np.asarray(canvas))
                    if i in (0,49,99,149,199,224):canvas.save(folder/f'paired_frame_{i+1:03d}.jpg',quality=94)
                    rows.append(np.asarray(canvas.resize((1440,320),Image.Resampling.LANCZOS)))
                whole.append_data(np.concatenate(rows,axis=0))
                if i%50==0:print(f'Paired video {i+1}/225',flush=True)
        finally:
            for writer in writers:writer.close()
    # Export readable report/media; retain raw PNG/GS/arrays in the run only.
    dest.mkdir(parents=True)
    for name in ('metrics_summary.json','baseline_five_scene_summary.json','paired_comparison_summary.json',
                 'metric_curves.png','all_scenes_comparison.mp4','paired_all_scenes_comparison.mp4',
                 'plan.json','status.json','selected_manifest.json','environment_and_code.json'):
        shutil.copy2(out/name,dest/name)
    details=('> 这是原始运行说明的离线阅读副本。下面的原始文件清单描述服务器运行目录；'
             '本报告包包含所有引用的图片、视频和指标，但不包含完整逐帧 PNG、深度数组或 GS 模型。\n\n'
             +(out/'README.md').read_text())
    (dest/'hybrid_details.md').write_text(details)
    (dest/'hybrid_details.html').write_text(html(details))
    for name in ('verification.json','timing_summary.json','qualitative_observations.json'):
        if (out/name).exists():shutil.copy2(out/name,dest/name)
    observations_path=out/'qualitative_observations.json'
    observations=json.loads(observations_path.read_text()) if observations_path.exists() else {}
    lines=['# DL3DV 五场景：WorldWarp 与三项目组合配对评测','',
        '相同五场景、相同输入像素、相同参考相机和相同扩散参数。三项目方法为 MapAnything → 一次 GaME 静态建模 / 渲染 → WorldWarp。两者采用 225 帧、720×480、30 fps（播放 7.5 秒）、strength .8、后续上下文 5、50 步采样、CFG 5、seed 32。','',
        '新方法额外用首图单独 TTT3R 深度校准一个全局尺度，不使用参考序列深度。GaME 拟合 500 步加 50 步预热、seed 0；这是历史三项目架构的基准适配版，不是 B 的 .6/ctx1 原配置。Qwen 按各自生成历史自动描述，后续文本可能不同。','',
        '[五场景同步同屏视频](paired_all_scenes_comparison.mp4)：每行一个场景，每行从左到右为真实 / WorldWarp 基线 / 三项目。','',
        '## 第 50 / 200 帧，五场景等权汇总','',
        '| 帧 | 方法 | PSNR ↑ dB | SSIM ↑ | LPIPS ↓ | R_dist ↓ rad | t_dist ↓ | FID ↓ 诊断 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for ep in ('50','200'):
        for method,data in [('WorldWarp',baseline),('三项目',summary)]:
            m=data['endpoints'][ep]
            lines.append(f'| {ep} | {method} | {m["psnr_db"]:.3f} | {m["ssim"]:.4f} | {m["lpips"]:.4f} | {m["R_dist_rad"]:.4f} | {m["t_dist"]:.4f} | {m["FID_endpoint_diagnostic"]:.3f} |')
    lines+=['','基线汇总直接读取之前两批结果，并合并特征重算 FID，没有重新生成基线视频，也没有平均两批 FID。每端点只有 5 张图，FID 仅作诊断；这不是论文官方复现。t_dist 为归一化平移误差，不是时间或米。退化图像也可能使 DUSt3R 位姿估计不可靠。','',
            '[三项目完整指标及方法说明](hybrid_details.md) · [离线详情 HTML](hybrid_details.html) · [可机读对照](paired_comparison_summary.json)','']
    lines+=['数值改善的场景数如下；这不是统计显著性检验，也不代表所有画面均改善。FID 不作单场景比较。','',
            '| 帧 | PSNR | SSIM | LPIPS | R_dist | t_dist |',
            '|---|---:|---:|---:|---:|---:|']
    for ep in ('50','200'):
        lines.append('| '+ep+' | '+' | '.join(f'{wins[ep][m]}/{len(records)}' for m in METRICS)+' |')
    lines.append('')
    lines+=['## 这次对照的结论','',
        '三项目组合没有表现出一致优势。第 50 帧平均 PSNR / SSIM 略升，但 LPIPS 和 FID 变差；第 200 帧各项指标仍有取舍，平均平移误差明显增大。温室和汽车展厅后期保留了更多清晰内容，但目标视角仍不正确，汽车结构还发生了改写；建筑场景后期明显退化。','',
        '第 200 帧平均旋转误差的下降主要由汽车展厅贡献，另外四个场景的旋转误差均上升。原版汽车展厅已经严重退化，其位姿估计本身可能不可靠，因此不能把均值下降理解为普遍提升。餐厅的部分像素指标上升也没有对应到正确的房间布局。','',
        '这是五场景、单种子的整套管线比较，几何估计器、GS 渲染器、地图更新方式及后续自动文本均可能影响结果，不能单独归因于 GaME。若继续改进，优先检查深度尺度与平移投影、条件覆盖及可见性，再用固定文本和逐项消融区分影响。','']
    lines+=['## 固定 GaME 场景的条件覆盖','',
            '覆盖率为实际送入扩散的 GaME alpha ≥ 0.5 的像素比例，未计后续 latent mask 腐蚀。空白区域依赖扩散补全；低覆盖率不等同于已经确定的失败原因。首图尺度系数只转换深度单位，不改相机轨迹或 MapAnything 的相对深度结构。','',
            '| 场景 | 深度尺度系数 | 首帧覆盖 | 第 50 帧覆盖 | 第 200 帧覆盖 |',
            '|---|---:|---:|---:|---:|']
    coverage={}
    for r in records:
        folder=r['folder']
        scale=json.loads((out/folder/'geometry/scale_calibration.json').read_text())
        guidance=json.loads((out/folder/'guidance/report.json').read_text())
        fractions=[guidance['renders'][i]['valid_fraction'] for i in (0,49,199)]
        coverage[folder]=dict(scale=scale['scale'],valid_fraction_1_50_200=fractions)
        lines.append(f'| {LABELS.get(folder,folder)} | {scale["scale"]:.4f} | {fractions[0]:.1%} | {fractions[1]:.1%} | {fractions[2]:.1%} |')
    dump(dest/'geometry_coverage.json',coverage)
    lines.append('')
    for r in records:
        folder=r['folder'];target=dest/folder;target.mkdir()
        for name in ('generated.mp4','ground_truth.mp4','comparison.mp4','paired_comparison.mp4',
                     'image_metrics.csv','image_metrics.json','pose_metrics.json','paired_input_provenance.json'):
            shutil.copy2(out/folder/name,target/name)
        shutil.copy2(r['base']/'generated.mp4',target/'baseline.mp4')
        for pattern in ('paired_frame_*.jpg','comparison_frame_*.jpg'):
            for src in (out/folder).glob(pattern):shutil.copy2(src,target/src.name)
        shutil.copy2(out/folder/'geometry/scale_calibration.json',target/'scale_calibration.json')
        lines += [f'## {LABELS.get(folder,folder)}','',f'场景 ID：`{r["scene_id"]}`','',
            f'[三列对比视频]({folder}/paired_comparison.mp4)','',
            '| 帧 | 方法 | PSNR ↑ | SSIM ↑ | LPIPS ↓ | R_dist ↓ rad | t_dist ↓ |',
            '|---|---|---:|---:|---:|---:|---:|']
        new_im=json.loads((out/folder/'image_metrics.json').read_text())
        new_po=json.loads((out/folder/'pose_metrics.json').read_text())
        for ep in ('50','200'):
            for label,im,po in [('WorldWarp',r['image'],r['pose']),('三项目',new_im,new_po)]:
                m=im['endpoints'][ep];p=po['endpoints'][ep]['generated']
                lines.append(f'| {ep} | {label} | {m["psnr_db"]:.3f} | {m["ssim"]:.4f} | {m["lpips"]:.4f} | {p["R_dist_rad"]:.4f} | {p["t_dist"]:.4f} |')
        if folder in observations:lines+=['',observations[folder].get('observation','')]
        lines+=['',f'![第 50 帧]({folder}/paired_frame_050.jpg)','',f'![第 200 帧]({folder}/paired_frame_200.jpg)','']
    lines+=['## 保存范围','',
        '下载整个本报告目录或对应 ZIP，可离线阅读 Markdown / HTML 和引用的所有图片视频。完整逐帧 PNG、GaME 模型、MapAnything 深度、逐帧 RGB/alpha 条件与日志保存在服务器运行目录；未保存逐次 GS 模型及逐去噪 latent。','',
        f'原始运行：`{out}`。','']
    if (out/'timing_summary.json').exists():
        timing=json.loads((out/'timing_summary.json').read_text())
        lines+=['## 本次耗时','',
                f'正式管线共 {timing["total_seconds"]/60:.1f} 分钟；起止时间 {timing["started_local"]} — {timing["finished_local"]}。不含适配代码开发、选场和随后报告打包。','',
                '| 阶段 | 分钟 |','|---|---:|']
        for stage,seconds in timing['stage_seconds'].items():lines.append(f'| {stage} | {seconds/60:.2f} |')
        lines.append('')
    md='\n'.join(lines)
    (dest/'README.md').write_text(md)
    (dest/'index.html').write_text(html(md))
    missing=[]
    for name in ('README.md','hybrid_details.md'):
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',(dest/name).read_text()):
            if not link.startswith(('http://','https://','#')) and not (dest/link).exists():missing.append(link)
    if missing:raise RuntimeError(f'Missing local report links: {missing}')
    dump(dest/'export_verification.json',dict(local_media_links_present=True,
        paired_input_hashes_match=True,scene_count=len(records),created_unix=time.time()))
    print(dest,flush=True)


if __name__=='__main__':main()
