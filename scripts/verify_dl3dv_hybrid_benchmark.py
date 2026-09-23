#!/usr/bin/env python3
"""Verify actual paired benchmark artifacts, frame indexing and metric aggregation."""
import argparse
import json
from pathlib import Path
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image

from worldwarp_benchmark import dump
from worldwarp_hybrid_benchmark import sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    args=parser.parse_args();out=args.run.resolve()
    plan=json.loads((out/'plan.json').read_text())
    status=json.loads((out/'status.json').read_text())
    summary=json.loads((out/'metrics_summary.json').read_text())
    assert status['status']=='complete' and summary['status']=='complete'
    assert len(summary['scenes'])==len(plan['inputs'])
    videos=[];image_rows=0;pngs=0;scene_metrics=[]
    for entry in plan['inputs']:
        folder=out/entry['scene_id'][:12]
        provenance=json.loads((folder/'paired_input_provenance.json').read_text())
        assert provenance['geometry_image_indices']==[0]
        assert not provenance['reference_depth_copied'] and not provenance['baseline_generated_images_copied']
        base=Path(entry['baseline_scene_dir'])
        for relative,digest in provenance['sha256'].items():
            assert sha256(folder/relative)==digest and sha256(base/relative)==digest
        for kind in ('gt','generated'):
            files=sorted((folder/kind).glob('*.png'))
            assert [f.name for f in files]==[f'{i:05d}.png' for i in range(225)]
            for path in files:
                with Image.open(path) as im:
                    assert im.size==(720,480)
                    im.verify()
            pngs+=len(files)
        image=json.loads((folder/'image_metrics.json').read_text())
        pose=json.loads((folder/'pose_metrics.json').read_text())
        generation=json.loads((folder/'generation/report.json').read_text())
        assert image['status']==pose['status']==generation['status']=='complete'
        assert [r['index'] for r in image['frames']]==list(range(225))
        image_rows+=len(image['frames'])
        assert len(generation['chunks'])==5 and generation['frames']==225
        calls=generation['geometry_bridge_calls'];assert len(calls)==5
        for i,call in enumerate(calls):
            assert call['global_target_indices']==list(range(i*44,i*44+49))
            assert call['context_frames']==(1 if i==0 else 5)
            assert not call['worldwarp_ttt3r_geometry_inference']
            assert not call['geometry_updates_from_generated_frames']
        scale=json.loads((folder/'geometry/scale_calibration.json').read_text())
        assert np.isfinite(scale['scale']) and scale['scale']>0
        assert not scale['held_out_depth_used'] and not scale['trajectory_changed']
        rgbd=np.load(folder/'geometry/posed_rgbd.npz')
        raw=np.load(folder/'mapanything/posed_rgbd.npz')
        np.testing.assert_allclose(rgbd['depth_z'],raw['depth_z']*scale['scale'])
        np.testing.assert_array_equal(rgbd['rgb'],np.array(Image.open(folder/'gt/00000.png'))[None])
        rendered=np.load(folder/'guidance/trajectory.npz')
        reference=np.load(folder/'reference_ttt3r_cameras.npz')
        for key in ('c2w','intrinsics'):np.testing.assert_array_equal(rendered[key],reference[key])
        assert np.load(folder/'guidance/warped_rgb.npy',mmap_mode='r').shape==(225,480,720,3)
        assert np.load(folder/'guidance/valid_alpha.npy',mmap_mode='r').shape==(225,480,720)
        fit=json.loads((folder/'scene/report.json').read_text())
        assert fit['checkpoint_reload_pass'] and fit['input_views']==1 and fit['gaussians']>0
        assert fit['camera_projection_test_max_error_px']<1e-3
        assert (folder/'scene/gaussians.ply').stat().st_size>0
        assert (folder/'scene/checkpoints/checkpoint.pth').stat().st_size>0
        for name,width in [('generated.mp4',720),('ground_truth.mp4',720),('comparison.mp4',1440)]:
            info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                '-show_entries','stream=nb_read_frames,r_frame_rate,width,height,duration','-of','json',str(folder/name)]))['streams'][0]
            assert (int(info['nb_read_frames']),info['width'],info['height'],info['r_frame_rate'])==(225,width,480,'30/1')
            videos.append(dict(file=f'{folder.name}/{name}',**info))
        scene_metrics.append((image,pose))
    for ep in ('50','200'):
        for key in ('psnr_db','ssim','lpips'):
            expected=np.mean([image['endpoints'][ep][key] for image,pose in scene_metrics])
            np.testing.assert_allclose(summary['endpoints'][ep][key],expected,rtol=1e-12,atol=1e-12)
        for key in ('R_dist_rad','t_dist'):
            expected=np.mean([pose['endpoints'][ep]['generated'][key] for image,pose in scene_metrics])
            np.testing.assert_allclose(summary['endpoints'][ep][key],expected,rtol=1e-12,atol=1e-12)
    timing=dict(started_local=datetime.fromtimestamp(status['started_unix'],ZoneInfo('Asia/Shanghai')).isoformat(),
        finished_local=datetime.fromtimestamp(status['finished_unix'],ZoneInfo('Asia/Shanghai')).isoformat(),
        total_seconds=status['finished_unix']-status['started_unix'],stage_seconds={},
        scope='Formal sequential GPU pipeline; excludes code preparation and later report export')
    for step in status['steps']:
        key=step['name'].split('_',1)[1] if '_' in step['name'] else step['name']
        timing['stage_seconds'][key]=timing['stage_seconds'].get(key,0)+step['finished_unix']-step['started_unix']
    dump(out/'timing_summary.json',timing)
    report=dict(status='passed',scenes=len(plan['inputs']),lossless_pngs=pngs,aligned_image_metric_rows=image_rows,
        paired_input_and_camera_hashes_match=True,actual_five_chunk_geometry_bridge_verified=True,
        geometry_uses_only_first_observed_image=True,global_depth_scale_verified=True,
        game_checkpoint_reload_and_projection_verified=True,aggregate_means_checked=True,video_probes=videos)
    dump(out/'verification.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='video_probes'},indent=2))


if __name__=='__main__':main()
