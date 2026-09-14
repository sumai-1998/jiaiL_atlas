#!/usr/bin/env python3
"""Launch the three classroom variants on idle GPUs 0, 1 and 2."""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    jobs, processes, logs = {}, {}, []
    assert json.loads((output/'geometry_smoke.json').read_text())['status'] == 'passed'
    for gpu, variant in enumerate(('rolling_gs', 'anchor_gs', 'anchor_points')):
        if (output/variant).exists():
            raise FileExistsError(output/variant)
        command = [str(root/'conda_envs/worldwarp/bin/python'), '-u',
            str(root/'scripts/generate_worldwarp_mapanything.py'), '--variant', variant,
            '--baseline', str(root/'WorldWarp_outputs/classroom_pan_left_2026-09-07'),
            '--first-rgbd', str(output/'shared_first_geometry/posed_rgbd.npz'),
            '--context-frames', '5', '--image', str(root/'Data/classroom.png'),
            '--output', str(output/variant), '--chunks', '4', '--strength', '0.6',
            '--gs-iterations', '500', '--seed', '32']
        env = os.environ.copy()
        env.update(CUDA_VISIBLE_DEVICES=str(gpu), PYTHONNOUSERSITE='1',
            HF_HOME=str(root/'hf_cache'), TORCH_HOME=str(root/'.cache/torch_geometry'),
            HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
            CUDA_HOME='/usr/local/cuda-12.8', OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4',
            MAX_JOBS='4', TOKENIZERS_PARALLELISM='false')
        env['PATH'] = '/usr/local/cuda-12.8/bin:' + env.get('PATH', '')
        env['LD_LIBRARY_PATH'] = '/usr/local/cuda-12.8/lib64:' + env.get('LD_LIBRARY_PATH', '')
        log = (output/f'{variant}.log').open('w')
        logs.append(log)
        process = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        processes[variant] = process
        jobs[variant] = dict(command=command, gpu=gpu, pid=process.pid, started_unix=time.time(), returncode=None)
    (output/'jobs.json').write_text(json.dumps(jobs, indent=2))
    while True:
        for name, process in processes.items():
            jobs[name]['returncode'] = process.poll()
            path = output/name/'report.json'
            if path.exists():
                try:
                    report = json.loads(path.read_text())
                    jobs[name]['status'] = report['status']
                    jobs[name]['completed_chunks'] = len(report['completed_chunks'])
                except json.JSONDecodeError:
                    pass
        (output/'jobs.json').write_text(json.dumps(jobs, indent=2))
        print(json.dumps({k:{q:v.get(q) for q in ('pid','returncode','status','completed_chunks')} for k,v in jobs.items()}), flush=True)
        if all(p.poll() is not None for p in processes.values()):
            break
        time.sleep(30)
    for log in logs:
        log.close()
    if any(p.returncode != 0 for p in processes.values()):
        raise SystemExit('One or more variants failed; inspect the separate logs.')


if __name__ == '__main__':
    main()
