#!/usr/bin/env python3
"""Run four isolated videos, plus their missing geometry diagnostics."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--gpus',default='1,2,5,6')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    assert json.loads((out/'smoke_native/validation.json').read_text())['status']=='passed'
    variants=('original','rolling_gs','anchor_gs','anchor_points')
    gpus=[int(x) for x in a.gpus.split(',')];assert len(gpus)==4 and len(set(gpus))==4
    usage=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.used','--format=csv,noheader,nounits'],text=True)
    used={int(x.split(',')[0]):int(x.split(',')[1]) for x in usage.strip().splitlines()}
    assert all(used[g]<128 for g in gpus),f'Selected GPU already occupied: {used}'
    assert shutil.disk_usage(out).free>700*1024**3,'Insufficient space for full iteration archives'
    baseline=ROOT/'WorldWarp_outputs/classroom_pan_left_2026-09-07'
    old=ROOT/'WorldWarp_outputs/classroom_hybrid_pan_left_2026-09-07'
    (out/'logs').mkdir(exist_ok=True);(out/'sources').mkdir(exist_ok=True)
    files=['scripts/classroom_geometry_trace.py','scripts/run_classroom_trace_variant.py',
        'scripts/mapanything_capture_all_frames.py','scripts/run_classroom_intermediate_capture.py',
        'scripts/validate_classroom_intermediates.py','scripts/test_classroom_geometry_trace.py',
        'scripts/mapanything_worldwarp_rgbd.py','scripts/worldwarp_map_geometry.py',
        'scripts/generate_worldwarp_mapanything.py','scripts/generate_worldwarp_rotation.py',
        'scripts/generate_worldwarp_hybrid_context.py','scripts/fuse_geometry_game.py',
        'scripts/game_render_trajectory.py','WorldWarp/pose_control.py','WorldWarp/src/ttt3r/ttt3r.py',
        'GaME/src/entities/game.py','GaME/src/flashsplat/scene/gaussian_model.py']
    sources=[]
    for name in files:
        target=out/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,target)
        sources.append(dict(path=name,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    (out/'sources/manifest.json').write_text(json.dumps(sources,indent=2))
    (out/'protocol.json').write_text(json.dumps(dict(
        input=str(ROOT/'Data/classroom.png'),variants=list(variants),gpus=gpus,
        frames=321,fps=30,chunks=4,total_yaw_degrees=-20,strength=.6,seed=32,
        context_frames=dict(original=1,rolling_gs=5,anchor_gs=5,anchor_points=5),
        sampling_steps=50,cfg=5,native_gs_iterations=500,
        gs_capture='Every optimization iteration plus initial model; full precision parameters, actual training RGB/alpha/depth, all component losses. Final optimizer state included.',
        video_capture='Every geometry target frame before threshold; exact pre-VAE RGB and masks; every uint8 generated frame before encoding.',
        ttt3r_capture='All input frames in four pipeline calls plus last generated chunk, with native raw predictions and processed depths/poses/K.',
        mapanything_capture='All actual inference views at native resolution, plus separate 321-frame diagnostic inference per F/G/H video in consecutive windows of 5.',
        game_capture='One rerun of the shared static scene, both 50-step warmup and 500-step fitting; all 321 final trajectory renders.',
        limitation='Rerun with matching settings and cached captions, not a bit-exact recovery of historical runs. No change to geometry source selection; extra all-frame predictions are diagnostic only.'),indent=2))
    jobs={};lock=threading.Lock()
    def persist():
        temp=out/'jobs.tmp';temp.write_text(json.dumps(jobs,indent=2));temp.replace(out/'jobs.json')
    def execute(key,command,gpu,envname='worldwarp'):
        env=os.environ.copy()
        env.update(CUDA_VISIBLE_DEVICES=str(gpu),PYTHONNOUSERSITE='1',HF_HOME=str(ROOT/'hf_cache'),
            TORCH_HOME=str(ROOT/'.cache/torch_geometry'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
            HF_HUB_DISABLE_TELEMETRY='1',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',
            MAX_JOBS='4',TOKENIZERS_PARALLELISM='false',WANDB_MODE='disabled',
            CLASSROOM_CAPTURE_MAP_NATIVE='1',CLASSROOM_CAPTURE_GAME_RENDER='1')
        if envname=='worldwarp':
            env['CUDA_HOME']='/usr/local/cuda-12.8'
            env['PATH']='/usr/local/cuda-12.8/bin:'+env.get('PATH','')
            env['LD_LIBRARY_PATH']='/usr/local/cuda-12.8/lib64:'+env.get('LD_LIBRARY_PATH','')
        cmd=[str(ROOT/f'conda_envs/{envname}/bin/python'),'-u']+[str(x) for x in command]
        with (out/'logs'/f'{key}.log').open('w') as log:
            process=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            with lock:
                jobs[key]=dict(status='running',command=cmd,gpu=gpu,pid=process.pid,started_unix=time.time());persist()
            code=process.wait()
            with lock:
                jobs[key].update(status='complete' if code==0 else 'failed',returncode=code,finished_unix=time.time());persist()
            if code:raise RuntimeError(f'{key} failed with {code}; see logs')
    def worker(variant,gpu):
        cmd=[ROOT/'scripts/run_classroom_trace_variant.py','--trace-variant',variant,
            '--trace-root',out/'traces'/variant,'--image',ROOT/'Data/classroom.png',
            '--output',out/variant,'--chunks','4','--strength','.6','--gs-iterations','500','--seed','32']
        if variant!='original':cmd+=['--baseline',baseline,'--context-frames','5']
        execute(variant,cmd,gpu)
        if variant!='original':
            execute(variant+'_all_frames',[ROOT/'scripts/mapanything_capture_all_frames.py',
                '--variant-output',out/variant],gpu,'mapanything')
        else:
            execute('game_fit',[ROOT/'scripts/run_classroom_trace_variant.py','--trace-variant','game',
                '--trace-root',out/'traces/game','--rgbd',old/'mapanything_dense/posed_rgbd.npz',
                '--output',out/'game_shared_scene','--max-views','1','--max-width','480',
                '--iterations','500'],gpu,'game')
            execute('game_render',[ROOT/'scripts/game_render_trajectory.py','--scene',out/'game_shared_scene',
                '--rgbd',old/'mapanything_dense/posed_rgbd.npz','--trajectory',baseline/'requested_camera_trajectory.npz',
                '--output',out/'game_shared_guidance'],gpu,'game')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(worker,v,g):v for v,g in zip(variants,gpus)}
        errors=[]
        while futures:
            done,_=concurrent.futures.wait(futures,timeout=30,return_when=concurrent.futures.FIRST_COMPLETED)
            for f in done:
                name=futures.pop(f)
                try:f.result()
                except Exception as e:errors.append(dict(variant=name,error=str(e)))
            with lock:print(json.dumps({k:v['status'] for k,v in jobs.items()}),flush=True)
        if errors:
            (out/'failures.json').write_text(json.dumps(errors,indent=2));raise RuntimeError(errors)
    (out/'inference_complete.json').write_text(json.dumps(dict(status='complete',jobs=jobs),indent=2))


if __name__=='__main__':main()
