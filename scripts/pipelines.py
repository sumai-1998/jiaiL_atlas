#!/usr/bin/env python3
"""One discoverable CLI for the locally deployed inference pipelines.

list / describe / plan use Python's standard library; run launches each model
in its own environment. Every run gets a plan, logs, and a machine-readable status.
"""
import argparse
import datetime
import json
import math
import os
import re
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=json.loads((ROOT/'pipelines/registry.json').read_text())
EXTENSIONS={'.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'}


def emit(obj): print(json.dumps(obj,ensure_ascii=False,indent=2),flush=True)
def write(path,obj):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2));tmp.replace(path)
def resolve_pipeline(name):
    for p in REGISTRY['pipelines']:
        if name.casefold() in [v.casefold() for v in [p['id'],*p['aliases']]]:return dict(p)
    raise ValueError(f'Unknown pipeline {name!r}; use: python scripts/pipelines.py list')
def python_for(name):
    return str(Path(os.environ.get('GIL_'+name.upper()+'_PYTHON',str(ROOT/f'conda_envs/{name}/bin/python'))).expanduser().absolute())
def stage_env(name,gpu):
    env=os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES=str(gpu),PYTHONNOUSERSITE='1',HF_HOME=str(ROOT/'hf_cache'),
               TORCH_HOME=str(ROOT/'.cache/torch_geometry'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
               HF_HUB_DISABLE_TELEMETRY='1',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MAX_JOBS='4',
               WANDB_MODE='disabled',TOKENIZERS_PARALLELISM='false',
               GIL_MAPANYTHING_PYTHON=python_for('mapanything'))
    default='/usr/local/cuda-12.8' if name=='worldwarp' else '/usr/local/cuda-12.4'
    cuda=Path(os.environ.get('GIL_CUDA_'+name.upper(),default))
    if cuda.is_dir():
        env.update(CUDA_HOME=str(cuda),PATH=str(cuda/'bin')+os.pathsep+env.get('PATH',''),
                   LD_LIBRARY_PATH=str(cuda/'lib64')+os.pathsep+env.get('LD_LIBRARY_PATH',''))
    # Editable installs are convenient locally; explicit project paths also work
    # after relocating the checkout without relying on stale editable .pth paths.
    project={'worldwarp':'WorldWarp','mapanything':'MapAnything','game':'GaME'}[name]
    env['PYTHONPATH']=os.pathsep.join([str(ROOT/project),str(ROOT/'scripts'),env.get('PYTHONPATH','')])
    return env
def expand_images(inputs):
    found=[]
    for value in inputs:
        p=Path(value).expanduser().resolve()
        if p.is_dir():found.extend(sorted(x for x in p.iterdir() if x.is_file() and x.suffix.lower() in EXTENSIONS))
        elif p.is_file() and p.suffix.lower() in EXTENSIONS:found.append(p)
        else:raise ValueError(f'Image/directory not found or unsupported: {p}')
    found=list(dict.fromkeys(found))
    if not found:raise ValueError('No images found')
    return found


def build_plan(args):
    p=resolve_pipeline(args.pipeline);images=expand_images(args.input)
    output=Path(args.output).expanduser().resolve()
    if output.exists():raise FileExistsError(f'Output already exists; choose a new directory: {output}')
    if p['kind']=='video' and len(images)!=1:
        raise ValueError('Video pipelines accept one image per run; use one output directory per image. Geometry pipelines accept multiple views.')
    if args.chunks!=4:raise ValueError('Unified video adapters currently expose the verified four-chunk contract: 321 frames / 10.7 s total.')
    if args.capture=='full' and not p['full_capture']:raise ValueError(f'{p["id"]} does not expose full capture; supported: A/F/G/H')
    if args.posthoc and not p.get('variant'):raise ValueError('--posthoc is for F/G/H final-frame MapAnything diagnostics only')
    if p['kind']=='video' and args.map_variant!='default':raise ValueError('--map-variant applies to geometry-only pipelines; video adapters use the default checkpoint')
    strength=p.get('strength',0.6) if args.strength is None else args.strength
    context=p.get('context_frames',1) if args.context_frames is None else args.context_frames
    if not math.isfinite(strength) or not 0<=strength<=1:raise ValueError('strength must be finite and in [0,1]')
    if context not in (1,5,9,13,17,21,25):raise ValueError('context-frames must be one of 1,5,9,13,17,21,25')
    if p['id'] in ('ww-rotate','ww-translate') and context!=1:raise ValueError('Original WorldWarp entry uses context=1; choose a Map/GaME pipeline for extended context')
    if not math.isfinite(args.angle) or not -90<args.angle<0:raise ValueError('Left rotation requires -90 < angle < 0')
    if not math.isfinite(args.dx) or args.dx>=0:raise ValueError('Left translation requires finite dx < 0')
    if min(args.gs_iterations,args.sampling_steps,args.max_views)<1 or not math.isfinite(args.cfg) or args.cfg<0:raise ValueError('Positive iteration/view counts and finite nonnegative CFG required')
    if args.gpu is not None and not re.fullmatch(r'(\d+|GPU-[A-Za-z0-9-]+)',args.gpu):raise ValueError('--gpu must identify one GPU, e.g. 1 or GPU-UUID')
    motion='The camera translates left at constant speed with fixed orientation, without rotation or zoom.' if p.get('motion')=='truck-left' else 'The camera stays at a fixed position and rotates left at constant angular speed without translation, tilt, roll or zoom.'
    prompt=args.prompt or 'Photorealistic view of the provided image. Preserve the scene, objects, materials, geometry and lighting. All objects remain stationary. '+motion
    caption_file=output/'caption.txt';reference=output/'reference';video=output/'video'
    steps=[]
    def add(name,env,script,*argv):
        steps.append(dict(name=name,environment=env,command=[python_for(env),'-u',str(ROOT/'scripts'/script),*[str(x) for x in argv]]))
    common=['--image',images[0],'--output',video,'--chunks','4','--width','480','--height','608',
            '--strength',str(strength),'--gs-iterations',str(args.gs_iterations),'--seed',str(args.seed),
            '--sampling-steps',str(args.sampling_steps),'--cfg',str(args.cfg),'--prompt',prompt,'--caption-file',caption_file]
    if p['kind']=='geometry':
        add('mapanything','mapanything','infer_geometry.py','--images',*images,'--output',output/'geometry',
            '--source-kind',args.source_kind,'--max-views',args.max_views,'--variant',args.map_variant)
        if p['id']=='mapanything-game':
            add('game_fit','game','fuse_geometry_game.py','--rgbd',output/'geometry/posed_rgbd.npz','--output',output/'scene',
                '--max-views',args.max_views,'--max-width','480','--iterations',args.gs_iterations)
    elif p['id']=='ww-translate':
        add('worldwarp','worldwarp','generate_worldwarp_translation.py',*common,'--dx',args.dx)
    else:
        add('prepare_reference','worldwarp','pipeline_reference.py','--image',images[0],'--output',reference,
            '--caption-file',caption_file,'--total-angle-deg',args.angle)
        common+=['--total-angle-deg',str(args.angle)]
        if p.get('variant'):
            tail=['--baseline',reference,'--context-frames',context,*common]
            if args.capture=='full':
                add('worldwarp','worldwarp','run_classroom_trace_variant.py','--trace-variant',p['variant'],
                    '--trace-root',output/'traces',*tail)
            else:add('worldwarp','worldwarp','generate_worldwarp_mapanything.py','--variant',p['variant'],*tail)
            if args.posthoc:
                add('posthoc_mapanything','mapanything','mapanything_capture_all_frames.py','--variant-output',video)
        elif p['id']=='ww-rotate':
            if args.capture=='full':
                add('worldwarp','worldwarp','run_classroom_trace_variant.py','--trace-variant','original',
                    '--trace-root',output/'traces','--trace-baseline',reference,*common)
            else:add('worldwarp','worldwarp','generate_worldwarp_rotation.py',*common)
        else:
            add('mapanything','mapanything','mapanything_calibrated_rgbd.py','--image',reference/'input_prepared.png',
                '--trajectory',reference/'requested_camera_trajectory.npz','--output',output/'geometry')
            add('game_fit','game','fuse_geometry_game.py','--rgbd',output/'geometry/posed_rgbd.npz','--output',output/'scene',
                '--max-views','1','--max-width','480','--iterations',args.gs_iterations)
            add('game_render','game','game_render_trajectory.py','--scene',output/'scene','--rgbd',output/'geometry/posed_rgbd.npz',
                '--trajectory',reference/'requested_camera_trajectory.npz','--output',output/'guidance')
            add('worldwarp','worldwarp','generate_worldwarp_hybrid_context.py','--guidance-dir',output/'guidance',
                '--baseline',reference,'--context-frames',context,*common)
    return dict(schema_version=1,pipeline=p['id'],pipeline_definition=p,inputs=[str(x) for x in images],output=str(output),
        gpu=args.gpu,prompt=prompt,parameters=dict(strength=strength,context_frames=context,gs_iterations=args.gs_iterations,
            sampling_steps=args.sampling_steps,cfg=args.cfg,seed=args.seed,angle=args.angle,dx=args.dx,capture=args.capture,
            posthoc=args.posthoc,source_kind=args.source_kind,map_variant=args.map_variant),
        video_contract=REGISTRY['video_contract'] if p['kind']=='video' else None,steps=steps,
        notes=['Prepared references contain camera/image/text only; no baseline video generation is required.',
               'New inputs use the supplied/generic prompt; historical classroom captions are not silently reused.',
               'Default parameters match historical families, not bit-exact historical results.'])


def preflight(plan):
    p=plan['pipeline_definition'];checks=[]
    def add(label,path):checks.append(dict(check=label,path=str(path),ok=Path(path).exists()))
    for env in p['environments']:add(env+' Python',python_for(env))
    if 'worldwarp' in p['environments']:
        for path in ['WorldWarp/ckpt/worldwarp_latest.ckpt','WorldWarp/ckpt/Wan-AI/Wan2.1-T2V-1.3B-Diffusers/model_index.json']:
            add('WorldWarp weight/config',ROOT/path)
        # GaME context wrapper still loads the upstream TTT3R object, even though
        # its geometry inference is replaced by fixed GaME renders.
        if not p.get('variant'):add('TTT3R weight',ROOT/'WorldWarp/src/ttt3r/cut3r_512_dpt_4_64.pth')
    if 'mapanything' in p['environments']:
        variant=plan['parameters']['map_variant'] if p['kind']=='geometry' else 'default'
        add('MapAnything weight',ROOT/f'checkpoints/{"mapanything-apache" if variant=="apache" else "mapanything"}/model.safetensors')
    checks.append(dict(check='ffmpeg',ok=shutil.which('ffmpeg') is not None))
    checks.append(dict(check='ffprobe',ok=shutil.which('ffprobe') is not None))
    return checks


def verify_outputs(plan):
    out=Path(plan['output']);p=plan['pipeline_definition']
    if p['kind']=='video':
        report=json.loads((out/'video/report.json').read_text())
        if report.get('status')!='complete':raise RuntimeError('Video report is not complete')
        video=Path(report['output_video'])
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
            '-show_entries','stream=nb_read_frames,r_frame_rate,width,height,duration','-of','json',str(video)]))['streams'][0]
        if (int(info['nb_read_frames']),info['r_frame_rate'],info['width'],info['height'])!=(321,'30/1',480,608):
            raise RuntimeError(f'Video contract mismatch: {info}')
        return dict(output_video=str(video),video_probe=info,intermediates=str(out/'video'))
    required=[out/'geometry/posed_rgbd.npz',out/'geometry/report.json']
    if p['id']=='mapanything-game':required += [out/'scene/gaussians.ply',out/'scene/checkpoints/checkpoint.pth',out/'scene/report.json']
    for path in required:
        if not path.is_file() or path.stat().st_size==0:raise RuntimeError(f'Missing output {path}')
    return dict(files=[str(x) for x in required])


def run(plan):
    if plan['gpu'] is None:raise ValueError('run requires --gpu after checking nvidia-smi; plan does not reserve a GPU')
    checks=preflight(plan)
    if any(not x['ok'] for x in checks):
        emit(dict(status='preflight_failed',checks=checks));return 2
    out=Path(plan['output']);out.mkdir(parents=True,exist_ok=False)
    (out/'logs').mkdir();(out/'caption.txt').write_text(plan['prompt'])
    write(out/'plan.json',plan);write(out/'preflight.json',checks)
    status=dict(status='running',pipeline=plan['pipeline'],started_unix=time.time(),steps=[],outputs=None)
    write(out/'status.json',status)
    child=None
    try:
        for step in plan['steps']:
            log=out/'logs'/(step['name']+'.log')
            row=dict(name=step['name'],status='running',log=str(log),started_unix=time.time())
            status['steps'].append(row);write(out/'status.json',status)
            print(f'[{step["name"]}] {log}',flush=True)
            with log.open('w') as stream:
                child=subprocess.Popen(step['command'],cwd=ROOT,env=stage_env(step['environment'],plan['gpu']),stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                row['pid']=child.pid;write(out/'status.json',status)
                code=child.wait()
            child=None
            row.update(returncode=code,finished_unix=time.time(),status='complete' if code==0 else 'failed')
            write(out/'status.json',status)
            if code:raise RuntimeError(f'Stage {step["name"]} failed with exit {code}; see {log}')
        status.update(status='complete',outputs=verify_outputs(plan),finished_unix=time.time())
    except (Exception,KeyboardInterrupt) as exc:
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        status.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=str(exc),finished_unix=time.time())
        write(out/'status.json',status);emit(status);return 130 if isinstance(exc,KeyboardInterrupt) else 1
    write(out/'status.json',status);emit(status);return 0


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    subs=p.add_subparsers(dest='action',required=True)
    subs.add_parser('list',help='Machine-readable pipeline registry')
    q=subs.add_parser('describe');q.add_argument('pipeline')
    q=subs.add_parser('status');q.add_argument('output',type=Path)
    for action in ['plan','run','doctor']:
        q=subs.add_parser(action)
        q.add_argument('--pipeline',required=True)
        q.add_argument('--input',nargs='+',required=True,help='One image for video; image files/directory for geometry')
        q.add_argument('--output',required=True,help='A new run directory; existing directories are rejected')
        q.add_argument('--gpu',help='One explicit GPU index or GPU UUID; required for run')
        q.add_argument('--prompt',help='Describe this scene and the intended static motion; defaults to a scene-neutral instruction')
        q.add_argument('--chunks',type=int,default=4)
        q.add_argument('--angle',type=float,default=-20,help='Total negative Y angle for rotation pipelines')
        q.add_argument('--dx',type=float,default=-0.002,help='Negative X displacement per frame, for ww-translate only')
        q.add_argument('--strength',type=float)
        q.add_argument('--context-frames',type=int)
        q.add_argument('--gs-iterations',type=int,default=500)
        q.add_argument('--sampling-steps',type=int,default=50)
        q.add_argument('--cfg',type=float,default=5)
        q.add_argument('--seed',type=int,default=32)
        q.add_argument('--capture',choices=['standard','full'],default='standard')
        q.add_argument('--posthoc',action='store_true',help='F/G/H only: estimate every final video frame after generation')
        q.add_argument('--max-views',type=int,default=8,help='Geometry-only input view limit')
        q.add_argument('--source-kind',choices=['observed','rendered','generated','unknown'],default='observed')
        q.add_argument('--map-variant',choices=['default','apache'],default='default',help='Geometry-only checkpoint choice')
    return p


def main(argv=None):
    p=parser();a=p.parse_args(argv)
    try:
        if a.action=='list':emit(REGISTRY);return 0
        if a.action=='describe':emit(resolve_pipeline(a.pipeline));return 0
        if a.action=='status':emit(json.loads((a.output/'status.json').read_text()));return 0
        plan=build_plan(a)
        if a.action=='plan':emit(plan);return 0
        if a.action=='doctor':
            checks=preflight(plan);ok=all(x['ok'] for x in checks)
            emit(dict(status='ready' if ok else 'missing_dependencies',checks=checks,
                      note='Read-only path/tool check, not a GPU import/kernel or inference validation.'));return 0 if ok else 2
        return run(plan)
    except (ValueError,OSError,KeyError) as exc:
        print(str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
