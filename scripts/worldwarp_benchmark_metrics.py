"""Explicit, reproducible metric definitions for the local WorldWarp pilot."""
import csv
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from worldwarp_benchmark import ROOT, N_FRAMES, dump


def frechet_low_rank(x, y):
    """Exact empirical FID via covariance factors, stable even when n << 2048."""
    x,y=np.asarray(x,dtype=np.float64),np.asarray(y,dtype=np.float64)
    if min(len(x),len(y))<2:raise ValueError('FID needs at least two samples per distribution')
    mx,my=x.mean(0),y.mean(0)
    a,b=(x-mx)/np.sqrt(len(x)-1),(y-my)/np.sqrt(len(y)-1)
    cross=np.linalg.svd(a@b.T,compute_uv=False).sum()
    return float(max(0, np.sum((mx-my)**2)+np.sum(a*a)+np.sum(b*b)-2*cross))


def pose_distances(pred, target):
    """First-camera-relative rotations; each translation track has unit max radius."""
    pred=np.linalg.inv(pred[0])@pred
    target=np.linalg.inv(target[0])@target
    r=pred[:,:3,:3]@np.swapaxes(target[:,:3,:3],-1,-2)
    angle=np.arccos(np.clip((np.trace(r,axis1=1,axis2=2)-1)/2,-1,1))
    p,t=pred[:,:3,3],target[:,:3,3]
    ps,ts=float(np.linalg.norm(p,axis=1).max()),float(np.linalg.norm(t,axis=1).max())
    if min(ps,ts)<1e-8:raise ValueError('Cannot normalize a stationary translation track')
    translation=np.linalg.norm(p/ps-t/ts,axis=1)
    return angle,translation,dict(pred_max_radius=ps,gt_max_radius=ts)


def image_metrics(args):
    import torch
    import lpips
    from pytorch_fid.inception import InceptionV3
    from skimage.metrics import structural_similarity
    from PIL import Image, ImageDraw
    import imageio.v2 as imageio
    torch.set_num_threads(4)
    perceptual=lpips.LPIPS(net='alex',version='0.1').eval().cuda()
    inception=InceptionV3([3]).eval().cuda()
    rows=[]; feats={'gt':[],'generated':[]}
    out=args.output
    def tensor(images):
        return torch.from_numpy(np.stack(images)).permute(0,3,1,2).float().cuda()/255
    with imageio.get_writer(out/'comparison.mp4',fps=30,codec='libx264',quality=9,macro_block_size=1) as writer:
        for start in range(0,N_FRAMES,4):
            indices=range(start,min(N_FRAMES,start+4))
            gt=[np.array(Image.open(out/'gt'/f'{i:05d}.png')) for i in indices]
            gen=[np.array(Image.open(out/'generated'/f'{i:05d}.png')) for i in indices]
            a,b=tensor(gt),tensor(gen)
            with torch.no_grad():
                scores=perceptual(a*2-1,b*2-1).flatten().cpu().numpy()
                feats['gt'].append(inception(a)[0].flatten(1).cpu().numpy())
                feats['generated'].append(inception(b)[0].flatten(1).cpu().numpy())
            for i,g,p,lp in zip(indices,gt,gen,scores):
                gf,pf=g.astype(np.float64)/255,p.astype(np.float64)/255
                mse=np.mean((gf-pf)**2)
                psnr=float(-10*np.log10(mse)) if mse>0 else None
                ssim=float(structural_similarity(gf,pf,data_range=1,channel_axis=2,
                    gaussian_weights=True,sigma=1.5,use_sample_covariance=False))
                rows.append(dict(index=i,frame_number=i+1,psnr_db=psnr,ssim=ssim,lpips=float(lp)))
                canvas=Image.fromarray(np.concatenate([g,p],axis=1));d=ImageDraw.Draw(canvas)
                d.rectangle((0,0,1440,25),fill='black')
                d.text((8,5),f'Ground truth | frame {i+1}',fill='white')
                d.text((728,5),'WorldWarp',fill='white')
                writer.append_data(np.array(canvas))
                if i in (0,49,99,149,199,224):canvas.save(out/f'comparison_frame_{i+1:03d}.jpg',quality=94)
            print(f'Image metrics: {len(rows)}/{N_FRAMES}',flush=True)
    with (out/'image_metrics.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    np.savez_compressed(out/'inception_features.npz',**{k:np.concatenate(v) for k,v in feats.items()})
    dump(out/'image_metrics.json',dict(status='complete',frames=rows,
        endpoints={str(n):rows[n-1] for n in (50,200)},
        mean_novel_1_to_224={k:float(np.mean([r[k] for r in rows[1:]])) for k in ('psnr_db','ssim','lpips')},
        settings=dict(pixel_range=[0,1],psnr='RGB MSE, 10*log10(1/MSE)',
            ssim='skimage Gaussian sigma=1.5, 11x11, population covariance, RGB mean',
            lpips='lpips 0.1.4, alex, version 0.1, RGB [-1,1]',
            fid='pytorch-fid 0.3.0 TensorFlow-compatible Inception-v3 pool3 2048-D; default resize/normalize',
            full_image=True,alignment='No image registration or post-generation matching',
            compression='PNG before video encoding')))


def pose_metrics(args):
    import hashlib
    import torch
    sys.path.insert(0,str(args.dust3r_root))
    from dust3r.inference import inference
    from dust3r.model import AsymmetricCroCo3DStereo
    from dust3r.utils.image import load_images
    from dust3r.image_pairs import make_pairs
    from dust3r.cloud_opt import global_aligner,GlobalAlignerMode
    torch.manual_seed(32);np.random.seed(32);torch.set_num_threads(4)
    checkpoint=ROOT/'checkpoints/dust3r/DUSt3R_ViTLarge_BaseDecoder_512_dpt.pth'
    # The official local checkpoint stores an argparse namespace; PyTorch 2.6+
    # changed the default. Restrict this compatibility override to this one file.
    original_load=torch.load
    def checkpoint_load(path,*a,**kw):
        if Path(path).resolve()==checkpoint.resolve():kw['weights_only']=False
        return original_load(path,*a,**kw)
    torch.load=checkpoint_load
    try:model=AsymmetricCroCo3DStereo.from_pretrained(str(checkpoint)).cuda().eval()
    finally:torch.load=original_load
    out=args.output
    gt=np.load(out/'dataset_cameras.npz')['c2w'].astype(np.float64)
    conditioning=np.load(out/'reference_ttt3r_cameras.npz')['c2w'].astype(np.float64)
    report=dict(status='running',estimator='DUSt3R_ViTLarge_BaseDecoder_512_dpt',
        checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        code_commit=subprocess.check_output(['git','-C',str(args.dust3r_root),'rev-parse','HEAD'],text=True).strip(),
        settings=dict(image_size=512,scene_graph='complete, symmetrized',batch_size=1,
            global_alignment='PointCloudOptimizer, MST init, 300 iterations, cosine, lr=0.01',
            frame_selection='Source index 0 plus indices 9,19,...,49 or 199',
            translation='Each trajectory separately divided by its maximum distance from its first camera, over this endpoint window',
            rotation_unit='radians',gt_poses='DL3DV calibrated OpenCV c2w',
            no_alignment_to_gt='No Procrustes or rotation fit to GT; only first-camera rebasing'), endpoints={})
    for endpoint in (50,200):
        indices=[0,*range(9,endpoint,10)]
        row=dict(indices=indices)
        for kind in ('generated','gt'):
            started=time.monotonic()
            images=load_images([str(out/kind/f'{i:05d}.png') for i in indices],size=512,verbose=False)
            pairs=make_pairs(images,scene_graph='complete',prefilter=None,symmetrize=True)
            output=inference(pairs,model,'cuda',batch_size=1,verbose=True)
            scene=global_aligner(output,device='cuda',mode=GlobalAlignerMode.PointCloudOptimizer)
            loss=scene.compute_global_alignment(init='mst',niter=300,schedule='cosine',lr=.01)
            poses=scene.get_im_poses().detach().cpu().numpy().astype(np.float64)
            if not np.isfinite(poses).all():raise RuntimeError('Non-finite DUSt3R poses')
            np.savez_compressed(out/f'dust3r_{kind}_{endpoint}.npz',indices=indices,c2w=poses,
                focals=scene.get_focals().detach().cpu().numpy())
            angle,trans,scales=pose_distances(poses,gt[indices])
            diagnostic_angle,diagnostic_trans,_=pose_distances(poses,conditioning[indices])
            row[kind]=dict(R_dist_rad=float(angle[-1]),R_dist_deg=float(np.rad2deg(angle[-1])),
                t_dist=float(trans[-1]),mean_R_rad=float(angle[1:].mean()),mean_t=float(trans[1:].mean()),
                all_R_rad=angle.tolist(),all_t=trans.tolist(),normalization=scales,
                alignment_loss=float(loss),seconds=time.monotonic()-started,
                against_conditioning_TTT3R_DIAGNOSTIC=dict(R_dist_rad=float(diagnostic_angle[-1]),t_dist=float(diagnostic_trans[-1])))
            del scene,output,pairs,images;torch.cuda.empty_cache()
        angle,trans,scales=pose_distances(conditioning[indices],gt[indices])
        row['reference_camera_error']=dict(R_dist_rad=float(angle[-1]),t_dist=float(trans[-1]),normalization=scales)
        report['endpoints'][str(endpoint)]=row
        dump(out/'pose_metrics.json',report)
    report['status']='complete';dump(out/'pose_metrics.json',report)


def make_report(args):
    import imageio.v2 as imageio
    from PIL import Image
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=args.output; plan=json.loads((out/'plan.json').read_text())
    observation_file=out/'qualitative_observations.json'
    observations=json.loads(observation_file.read_text()) if observation_file.is_file() else {}
    status=json.loads((out/'status.json').read_text())
    stage_seconds={s['name']:s['finished_unix']-s['started_unix'] for s in status['steps'] if s.get('status')=='complete'}
    records=[];features=[]
    for item in plan['inputs']:
        folder=out/item['scene_id'][:12]
        records.append(dict(scene_id=item['scene_id'],folder=folder.name,
            image=json.loads((folder/'image_metrics.json').read_text()),
            pose=json.loads((folder/'pose_metrics.json').read_text()),
            generation=json.loads((folder/'generation/report.json').read_text())))
        features.append(dict(np.load(folder/'inception_features.npz')))
    summary=dict(status='complete',official_reproduction=False,protocol='local-dl3dv-paper-based-pilot-v1',
        limitations=['Exact official test split and frame sampling are unpublished.',
            'Local 480x270 source frames are cropped/upscaled to 720x480.',
            'Endpoint FID has only one sample per scene and is diagnostic.',
            'LPIPS/SSIM/DUSt3R settings are fixed local choices; pose estimates may be unreliable on degraded frames.',
            'Generation history uses decoded uint8 RGB directly instead of MP4 round trips.'],
        scene_count=len(records),parameters=plan['parameters'],scenes=[],endpoints={})
    for r in records:
        if r['image']['status']!='complete' or r['pose']['status']!='complete':raise RuntimeError('Incomplete metrics')
        summary['scenes'].append(dict(scene_id=r['scene_id'],folder=r['folder'],
            image=r['image']['endpoints'],pose={k:v['generated'] for k,v in r['pose']['endpoints'].items()},
            generation=r['generation'],
            generation_seconds_including_model_loading=stage_seconds.get(r['folder']+'_generate'),
            generation_report_seconds_exclude_model_loading=True))
    for endpoint in (50,200):
        key=str(endpoint)
        mean={m:float(np.mean([r['image']['endpoints'][key][m] for r in records])) for m in ('psnr_db','ssim','lpips')}
        mean.update({m:float(np.mean([r['pose']['endpoints'][key]['generated'][m] for r in records])) for m in ('R_dist_rad','R_dist_deg','t_dist')})
        mean['FID_endpoint_diagnostic']=frechet_low_rank(np.stack([f['gt'][endpoint-1] for f in features]),np.stack([f['generated'][endpoint-1] for f in features]))
        mean['FID_sample_count']=len(records)
        summary['endpoints'][key]=mean
    summary['FID_all_novel_frames_diagnostic']=frechet_low_rank(np.concatenate([f['gt'][1:] for f in features]),np.concatenate([f['generated'][1:] for f in features]))
    summary['FID_all_novel_samples']=224*len(records)
    camera_audit={}
    for r in records:
        gt=np.load(out/r['folder']/'dataset_cameras.npz')
        ref=np.load(out/r['folder']/'reference_ttt3r_cameras.npz')
        g,t=gt['c2w'].astype(float),ref['c2w'].astype(float)
        camera_audit[r['folder']]={}
        for endpoint in (50,200):
            i=endpoint-1
            angle=np.rad2deg(np.arccos(np.clip((np.trace(g[i,:3,:3])-1)/2,-1,1)))
            error=np.rad2deg(np.arccos(np.clip((np.trace(t[i,:3,:3]@g[i,:3,:3].T)-1)/2,-1,1)))
            camera_audit[r['folder']][str(endpoint)]=dict(GT_net_rotation_deg_from_source=float(angle),
                TTT3R_reference_rotation_error_deg=float(error),
                reference_fx_over_dataset_fx=float(ref['intrinsics'][i,0,0]/gt['intrinsics'][i,0,0]))
    summary['camera_motion_audit']=camera_audit
    dump(out/'camera_motion_audit.json',camera_audit)
    dump(out/'metrics_summary.json',summary)
    fig,axes=plt.subplots(1,3,figsize=(15,4))
    for r in records:
        frames=r['image']['frames'][1:]
        for ax,key in zip(axes,('psnr_db','ssim','lpips')):
            ax.plot([f['frame_number'] for f in frames],[f[key] for f in frames],label=r['folder'])
            ax.set(xlabel='Frame number (source = 1)',ylabel=key);ax.grid(alpha=.2)
    for ax in axes:
        for boundary in (50,94,138,182):ax.axvline(boundary,color='gray',alpha=.25,linestyle=':')
    axes[0].legend(fontsize=7);fig.tight_layout();fig.savefig(out/'metric_curves.png',dpi=160);plt.close(fig)
    # All scenes spatially tiled: each row is GT | generated, no temporal concatenation.
    readers=[imageio.get_reader(out/r['folder']/'comparison.mp4') for r in records]
    with imageio.get_writer(out/'all_scenes_comparison.mp4',fps=30,codec='libx264',quality=9,macro_block_size=1) as writer:
        for frames in zip(*readers):writer.append_data(np.concatenate(frames,axis=0))
    for reader in readers:reader.close()
    count=len(records)
    dump(out/'selected_manifest.json',dict(scene_count=count,scenes=plan['inputs'],
        selection_description=plan.get('selection_description',
            '在生成前按本地清单 scene ID 排序固定选出，没有依据结果筛选。')))
    import shlex
    manifest_arg=shlex.quote(str(out/'selected_manifest.json'))
    lines=[f'# WorldWarp：DL3DV 本地 {count} 场景基准', '',
        f'这是一次按论文已公开方法建立的本地小样本基准，**不是论文官方结果复现**。本次 {count} 个场景：'+plan.get('selection_description','在生成前按本地清单 scene ID 排序固定选出，没有依据结果筛选。'), '',
        '[所有场景同时对比视频](all_scenes_comparison.mp4)：每行一个场景，左侧是真实帧，右侧是生成帧。225 帧、30 fps、播放时长 7.5 秒；30 fps 是播放速度，不代表原始采集时间。', '',
        '## 第 50 / 200 帧指标', '',
        '第一张输入图计为第 1 帧，因此第 50 / 200 帧分别对应数组索引 49 / 199。以下各场景等权平均，未使用图像配准、挑帧或去除失败案例。', '',
        f'| 帧 | PSNR↑ (dB) | SSIM↑ | LPIPS↓ | R_dist↓ (rad) | t_dist↓ | FID↓（仅 {count} 张，诊断） |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for endpoint,s in summary['endpoints'].items():
        lines.append(f'| {endpoint} | {s["psnr_db"]:.3f} | {s["ssim"]:.4f} | {s["lpips"]:.4f} | {s["R_dist_rad"]:.4f} | {s["t_dist"]:.4f} | {s["FID_endpoint_diagnostic"]:.3f} |')
    lines += ['', f'**FID 限制：**每个端点只有 {count} 张图，协方差秩至多为 {count-1}，数值不稳定，不能用于对照论文 FID 排名。全部新生成帧合并的 FID 也只是诊断，帧之间高度相关。',
        f'全部 {summary["FID_all_novel_samples"]} 张新生成帧的诊断 FID：{summary["FID_all_novel_frames_diagnostic"]:.3f}。', '',
        '![逐帧指标](metric_curves.png)', '', '## 本地轨迹的运动幅度', '',
        '下表均按第 50 / 200 帧的顺序列出。GT 角度是端点相对首帧的净旋转，不是累计转角，也不包含平移。不同场景的同一帧号不代表相同运动难度。论文未公开精确采样，因此不能把本地第 50 帧默认为与论文有相同的视角跨度。', '',
        '| 场景 | GT 净旋转（°） | TTT3R 参考相机相对 GT 的旋转误差（°） | 参考估计 / 数据集标定 f_x |',
        '|---|---:|---:|---:|']
    for r in records:
        audit=camera_audit[r['folder']];a,b=audit['50'],audit['200']
        lines.append(f'| {observations.get(r["folder"],{}).get("label",r["folder"])} | {a["GT_net_rotation_deg_from_source"]:.2f} / {b["GT_net_rotation_deg_from_source"]:.2f} | {a["TTT3R_reference_rotation_error_deg"]:.2f} / {b["TTT3R_reference_rotation_error_deg"]:.2f} | {a["reference_fx_over_dataset_fx"]:.3f} / {b["reference_fx_over_dataset_fx"]:.3f} |')
    lines += ['', '## 各场景', '']
    for r in records:
        folder=r['folder']
        observation=observations.get(r['folder'],{})
        lines += [f'### {observation.get("label",r["folder"])}', '',f'场景 ID：`{r["scene_id"]}`', '',
            f'[并排视频]({folder}/comparison.mp4) · [生成视频]({folder}/generated.mp4) · [真实视频]({folder}/ground_truth.mp4) · [逐帧 CSV]({folder}/image_metrics.csv)', '',
            '| 帧 | PSNR↑ | SSIM↑ | LPIPS↓ | R_dist↓ rad | t_dist↓ | GT 视频重建 R / t（估计器参照） |',
            '|---|---:|---:|---:|---:|---:|---:|']
        for ep in ('50','200'):
            im=r['image']['endpoints'][ep];po=r['pose']['endpoints'][ep];g=po['generated'];floor=po['gt']
            lines.append(f'| {ep} | {im["psnr_db"]:.3f} | {im["ssim"]:.4f} | {im["lpips"]:.4f} | {g["R_dist_rad"]:.4f} | {g["t_dist"]:.4f} | {floor["R_dist_rad"]:.4f} / {floor["t_dist"]:.4f} |')
        if observation.get('observation'):lines += ['', '画面抽查：'+observation['observation'], '']
        lines += ['',f'![第 50 帧]({folder}/comparison_frame_050.jpg)', '',f'![第 200 帧]({folder}/comparison_frame_200.jpg)', '']
    lines += ['## 实际流程与参数', '',
        '1. 从现有 pixelSplat 格式 DL3DV 分片读取相机和图片，按时间戳取前 225 帧。原图 480×270，经 Lanczos4 放大并中心裁剪到 720×480；内参应用同一像素变换，外参由 OpenCV w2c 转为 c2w，统一到第一帧坐标系。',
        '2. 遵循论文补充 §7，用 TTT3R 处理真实参考序列，提取生成所需的参考相机与内参。它产生的真实序列深度仅保存作诊断，**不输入生成的几何拟合或扩散模型**。这属于使用参考视频估计相机的评测设置，不是只给一张图且完全没有轨迹信息的设置。',
        '3. 生成器的实际图像输入只有第一张真实图。后续 TTT3R、GS 与 Qwen caption 只接收已生成的历史。TTT3R 读取上一段 49 帧；原生 warper 用末尾 5 个连续上下文视图初始化和拟合 GS，首段只用第 1 帧。这不是均匀抽取 5 个历史关键帧。使用原生 WorldWarp GS 与异步扩散，不接入 MapAnything 或 GaME。',
        '4. 5 段，每段 49 帧；首段上下文 1 帧，后续各重叠 5 个生成历史帧。拼接去重得到 49+4×44=225 帧。GS 500 步，位置学习率 1.6e-3；strength 0.8，采样 50 步，CFG 5，seed 32。Qwen 根据起始图及生成历史自动写 caption。',
        '5. 编码前保存生成 PNG，与相同索引、相同裁剪的真实 PNG 计算全图指标；输入帧不进入平均新视角分数。视频编码不参与评分。', '',
        '## 指标定义和不能直接对照论文的部分', '',
        '- PSNR：RGB [0,1] 均方误差转 dB；SSIM：11×11 高斯窗、sigma=1.5、总体协方差、RGB 通道平均。LPIPS：AlexNet、v0.1。论文未公开具体 SSIM 实现或 LPIPS 主干，因此此处固定定义用于后续本地比较。',
        '- FID：pytorch-fid 的标准 Inception-v3 2048 维特征。小样本用低秩协方差因子的等价公式计算，避免奇异矩阵开方；数学可计算不代表统计可靠。',
        '- 位姿：使用独立的官方 DUSt3R 512 DPT 权重，从生成图重建相机；不把请求相机直接当成生成相机。第 50 帧使用索引 0、9、19、29、39、49；第 200 帧使用 0、9、19、…、199。完整双向配对、MST 初始化、全局优化 300 步、cosine 调度、lr=0.01。各端点分别重建。',
        '- R_dist 按论文旋转测地距离，主表用弧度。t_dist 按 L2，先相对第一帧，然后预测和真值各除以各自轨迹内最远距离；没有再对 GT 做 Procrustes 拟合。论文没有公开具体归一化代码，因此这一定义需要固定后再比较其他管线，不能解释为米。',
        '- 另对真实视频使用同一 DUSt3R 过程，展示估计器自身的误差参照；这不是可直接减掉的噪声下界。pose_metrics.json 也保存 TTT3R 参考相机相对数据集相机的误差，以及生成相机相对 TTT3R 控制轨迹的诊断值。',
        '- 严重模糊或结构崩坏的生成画面也可能使 DUSt3R 位姿不可靠。给出有限数值仅表示重建过程完成，不等于相机一定恢复准确；真实视频上的估计误差也不能作为这些退化画面的误差上界。位姿分数需要结合图像指标和实际画面一起阅读。',
        '- 未公开的论文场景划分、采样间隔、相机评测代码不能复原。本次只代表这里固定的场景、现有低分辨率图片、前 225 帧顺序和本地代码。原始片段的实际采集帧率未从分片中确认，不能把此处 50 帧运动跨度假定为论文的同一跨度。', '',
        '- 本地适配器把上一段解码后的 uint8 RGB 直接作为下一段图像历史，不经过 MP4 再解码；caption 仍读取分段视频。这样避免把视频编码损失加入几何历史与评分，但与上游演示脚本的视频文件往返存在差异。原生 GS 与扩散算法保持上游实现。', '',
        '## 文件与复用', '',
        '- metrics_summary.json：可供 AI 工具读取的总表；每个场景 image_metrics.csv / image_metrics.json / pose_metrics.json：明细。',
        '- gt/、generated/：225 帧无损图片；dataset_cameras.npz、reference_ttt3r_cameras.npz：数据集与实际控制相机。',
        '- reference_ttt3r_depth_DIAGNOSTIC_ONLY.npy：参考视频深度，仅作诊断；generation/artifacts/：每段最终 GS、caption、扩散调度图、分段视频。没有逐 GS 迭代模型或逐去噪 latent。',
        '- dust3r_*.npz：真实与生成视频重建的相机；inception_features.npz：FID 特征。',
        '- plan.json、preflight.json、status.json、logs/：执行参数、状态与日志。下载整个本目录即可离线查看文档及所有引用的图片和视频。', '',
        '复跑入口（输出目录必须不存在，先检查 GPU）：', '', '```bash',
        f'python scripts/pipelines.py benchmark plan --manifest {manifest_arg} --count {count} --output runs/NEW_RUN --gpu GPU_ID',
        f'python scripts/pipelines.py benchmark doctor --manifest {manifest_arg} --count {count} --output runs/NEW_RUN --gpu GPU_ID',
        f'python scripts/pipelines.py benchmark run --manifest {manifest_arg} --count {count} --output runs/NEW_RUN --gpu GPU_ID',
        '```', '',
        '方法依据：[WorldWarp 论文 §5 与补充 §7](https://arxiv.org/html/2512.19678v1)、[官方代码](https://github.com/HyoKong/WorldWarp)、[DUSt3R 官方代码](https://github.com/naver/dust3r)、[LPIPS](https://github.com/richzhang/PerceptualSimilarity)、[pytorch-fid](https://github.com/mseitzer/pytorch-fid)。']
    (out/'README.md').write_text('\n'.join(lines)+'\n')
    import markdown
    import re
    body=markdown.markdown('\n'.join(lines),extensions=['tables','fenced_code'])
    body=re.sub(r'<a href="([^"]+\.mp4)">([^<]+)</a>',
        r'<a href="\1">\2</a><br><video controls preload="metadata" src="\1"></video>',body)
    (out/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>WorldWarp DL3DV 本地基准</title>'
        '<style>body{max-width:1200px;margin:32px auto;padding:0 18px;font:16px/1.7 system-ui,sans-serif;color:#17202a}'
        'img,video{max-width:100%;height:auto}video{display:block;margin:12px 0 28px;background:#111}'
        'table{border-collapse:collapse;display:block;overflow-x:auto}th,td{padding:8px 12px;border:1px solid #ddd}'
        'th{background:#eef2f6}pre{overflow:auto;background:#f3f5f7;padding:14px}a{color:#145da0}'
        'h2{margin-top:2em}h3{overflow-wrap:anywhere}</style><body>'+body+'</body></html>')
