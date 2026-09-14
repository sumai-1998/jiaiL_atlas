#!/usr/bin/env python3
"""Validate exhaustive iteration/frame coverage and create a navigable report."""
import argparse
import csv
import json
import subprocess
import zipfile
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();out=a.output.resolve()
    import numpy as np
    import torch
    torch.set_num_threads(4)
    from PIL import Image
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    baseline=out.parents[0]/'classroom_pan_left_2026-09-07'
    original_camera=np.load(baseline/'requested_camera_trajectory.npz')
    original_image=np.asarray(Image.open(baseline/'input_prepared.png'))
    variants=('original','rolling_gs','anchor_gs','anchor_points')
    rows=[];fits=[]
    for variant in variants:
        root=out/variant;trace=out/'traces'/variant
        assert json.loads((trace/'capture_complete.json').read_text())['status']=='complete'
        report=json.loads((root/'report.json').read_text());assert report['status']=='complete'
        camera=np.load(root/'requested_camera_trajectory.npz')
        for k in ('c2w','intrinsics','fps'):np.testing.assert_array_equal(camera[k],original_camera[k])
        np.testing.assert_array_equal(np.asarray(Image.open(root/'input_prepared.png')),original_image)
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames',
            '-show_entries','stream=width,height,avg_frame_rate,nb_read_frames,duration','-of','json',report['output_video']],text=True))
        stream=probe['streams'][0]
        assert (stream['width'],stream['height'],int(stream['nb_read_frames']))==(480,608,321)
        assert stream['avg_frame_rate']=='30/1' and abs(float(stream['duration'])-10.7)<1e-5
        frame_total=0;map_actual=0
        for i in range(4):
            chunk=trace/f'chunk_{i:03d}';n=81 if i==0 or variant=='original' else 85
            context=1 if i==0 or variant=='original' else 5
            global_start=i*80-(context-1)
            frame_index=[dict(local_frame=j,global_frame=global_start+j,
                conditioning_frame=j<context,retained_in_delivered_video=i==0 or j>=context)
                for j in range(n)]
            (chunk/'frame_index.json').write_text(json.dumps(frame_index,indent=2))
            for sub in ('raw_geometry_warp','diffusion_condition','generated_frames_before_codec'):
                m=json.loads((chunk/sub/'manifest.json').read_text())
                assert m['status']=='complete' and m['frames']==n,(chunk,sub)
            geom=np.load(chunk/'raw_geometry_warp/rgb.npy',mmap_mode='r')
            alpha=np.load(chunk/'raw_geometry_warp/alpha.npy',mmap_mode='r')
            cond=np.load(chunk/'diffusion_condition/rgb_float32.npy',mmap_mode='r')
            assert geom.shape==(1,n,3,608,480) and alpha.shape==(1,n,1,608,480)
            assert cond.shape==(n,608,480,3)
            assert len(list((chunk/'diffusion_condition/rgb').glob('*.png')))==n
            assert len(list((chunk/'diffusion_condition/mask').glob('*.png')))==n
            assert len(list((chunk/'generated_frames_before_codec').glob('*.png')))==n
            assert np.isfinite(geom).all() and np.isfinite(alpha).all() and np.isfinite(cond).all()
            frame_total+=n
            if variant!='original':
                native=root/'geometry'/f'chunk_{i:03d}'/'mapanything_native'
                manifest=json.loads((native/'manifest.json').read_text())
                expected=1 if i==0 else (5 if variant=='rolling_gs' or i==1 else 6)
                assert manifest['views']==expected
                for view in manifest['frames']:
                    vp=Path(view['directory'])
                    with np.load(vp/'prediction_arrays.npz') as z:
                        assert 'depth_z' in z.files and 'conf' in z.files
                        assert z['depth_z'].shape[1:3]==(518,406)
                    assert (vp/'prediction.pt').is_file() and (vp/'processed_input.pt').is_file()
                map_actual+=expected
        if variant=='original':
            for i in range(5):
                t=trace/f'chunk_{i:03d}'/'ttt3r'
                assert json.loads((t/'manifest.json').read_text())['frames']==81
                assert len(list((t/'frames').glob('*.npz')))==81
                assert len(list((t/'native_predictions').glob('*.pt')))==81
                assert np.load(t/'depth_z.npy',mmap_mode='r').shape==(81,608,480)
                index=[dict(local_frame=j,global_frame=0 if i==0 else (i-1)*80+j,
                    source_kind='repeated_input_image' if i==0 else 'decoded_generated_chunk',
                    diagnostic_only=i==4) for j in range(81)]
                (t/'frame_index.json').write_text(json.dumps(index,indent=2))
            all_frame_count=321
        else:
            diag=root/'mapanything_all_generated_frames'
            m=json.loads((diag/'manifest.json').read_text())
            assert m['status']=='complete' and m['frames']==321
            (diag/'progress.json').write_text(json.dumps(dict(status='complete',frames_completed=321,total=321)))
            assert sorted(x['global_frame'] for x in m['frame_index'])==list(range(321))
            allviews=list(diag.glob('window_*/mapanything_native/view_*'))
            assert len(allviews)==321
            assert all((x/'prediction_arrays.npz').is_file() and (x/'prediction.pt').is_file() for x in allviews)
            all_frame_count=len(allviews)
        rows.append(dict(variant=variant,video=report['output_video'],video_frames=321,
            geometry_target_frames_including_context=frame_total,actual_mapanything_views=map_actual,
            all_generated_frames_with_geometry=all_frame_count,video_probe=probe))
    for manifest in sorted((out/'traces').glob('*/**/*_fit_*/manifest.json')):
        fit=manifest.parent;m=json.loads(manifest.read_text());assert m['status']=='complete'
        n=m['iterations'];loss=[json.loads(x) for x in (fit/'losses.jsonl').read_text().splitlines()]
        assert [x['iteration'] for x in loss]==list(range(1,n+1))
        assert [x['render_model_iteration'] for x in loss]==list(range(n))
        for name,ext,start in (('models','pt',0),('training_renders','npz',1),('training_rgb','png',1)):
            expected={f'iteration_{i:06d}.{ext}' for i in range(start,n+1)}
            actual={x.name for x in (fit/name).glob(f'*.{ext}')}
            assert actual==expected,(fit,name,len(actual),len(expected))
        # Check every model archive's directory, and load first/middle/final tensors.
        for model in (fit/'models').glob('*.pt'):
            with zipfile.ZipFile(model) as z:
                assert any(x.endswith('/data.pkl') for x in z.namelist())
        for step in (0,n//2,n):
            data=torch.load(fit/'models'/f'iteration_{step:06d}.pt',map_location='cpu',weights_only=False)
            assert data['iteration']==step
            params=data.get('splats',data.get('tensors'))
            assert params and all(torch.isfinite(v).all() for v in params.values())
            required=({'means','scales','quats','opacities','sh0','shN'} if m['kind']=='native_gs'
                      else {'_xyz','_features_dc','_features_rest','_scaling','_rotation','_opacity'})
            assert required <= set(params),(fit,'missing Gaussian parameters')
        if m['kind']=='native_gs':
            variant=fit.parents[1].name;chunk=fit.parent.name
            if variant in ('rolling_gs','anchor_gs'):
                last=torch.load(fit/'models'/f'iteration_{n:06d}.pt',map_location='cpu',weights_only=False)['splats']
                final=torch.load(out/variant/'geometry'/chunk/'native_3dgs.pt',map_location='cpu',weights_only=False)['splats']
                for k in last:assert torch.equal(last[k],final[k]),(fit,k)
        with (fit/'losses.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(loss[0]));w.writeheader();w.writerows(loss)
        keys=[k for k in loss[0] if 'loss' in k]
        fig,ax=plt.subplots(figsize=(9,4))
        for k in keys:ax.plot([r['iteration'] for r in loss],[r[k] for r in loss],label=k,lw=.8)
        ax.set(xlabel='Optimization iteration',ylabel='Loss',title=str(fit.relative_to(out)))
        ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(fit/'losses.png',dpi=130);plt.close(fig)
        fits.append(dict(path=str(fit),kind=m['kind'],iterations=n,models=n+1,renders=n))
    assert len(fits)==14,(len(fits),fits)
    assert sum(f['iterations'] for f in fits)==6550
    game=out/'game_shared_guidance'
    assert {x.name for x in (game/'frames').glob('*.npz')}=={f'frame_{i:03d}.npz' for i in range(321)}
    assert len(list((game/'rgb_frames').glob('*.png')))==321
    result=dict(status='passed',variants=rows,fits=fits,gs_iterations=6550,gs_model_snapshots=6564,
        gs_training_renders=6550,gs_loss_rows=6550,mapanything_all_video_frames=963,
        game_trajectory_frames=321,ttt3r_inference_frames=405,
        validations='All frame/iteration indices contiguous; all checkpoint ZIP directories readable; first/middle/final tensors finite; F/G last snapshots equal final models; source image/trajectory equal old baseline; videos counted with ffprobe.')
    (out/'validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('variants','fits')}),flush=True)


if __name__=='__main__':main()
