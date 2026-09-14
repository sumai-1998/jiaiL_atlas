"""Small real-GPU check for complete, aligned GS recording and RNG preservation."""
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'WorldWarp'))


def main():
    import numpy as np
    import torch
    import classroom_geometry_trace as trace
    from worldwarp_map_geometry import render_geometry
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    trace.initialize(out/'trace')
    rgbd=ROOT/'WorldWarp_outputs/classroom_worldwarp_mapanything_2026-09-08/shared_first_geometry/posed_rgbd.npz'
    cam=np.load(rgbd);poses=cam['c2w'][:1];ks=cam['intrinsics'][:1]
    render_geometry(rgbd,poses,ks,'gs',out/'plain',iterations=3)
    rng_plain=torch.get_rng_state().clone();cuda_plain=torch.cuda.get_rng_state().clone()
    trace.install_worldwarp();trace.set_chunk(0)
    render_geometry(rgbd,poses,ks,'gs',out/'recorded',iterations=3)
    assert torch.equal(rng_plain,torch.get_rng_state())
    assert torch.equal(cuda_plain,torch.cuda.get_rng_state())
    trace.flush()
    fit=trace.FITS[0];m=json.loads((fit.path/'manifest.json').read_text())
    assert m['iterations']==3
    assert len(list((fit.path/'models').glob('*.pt')))==4
    assert len(list((fit.path/'training_renders').glob('*.npz')))==3
    rows=[json.loads(x) for x in (fit.path/'losses.jsonl').read_text().splitlines()]
    assert [x['render_model_iteration'] for x in rows]==[0,1,2]
    a=torch.load(out/'plain/native_3dgs.pt',map_location='cpu',weights_only=False)['splats']
    b=torch.load(out/'recorded/native_3dgs.pt',map_location='cpu',weights_only=False)['splats']
    deltas={k:float((a[k]-b[k]).abs().max()) if a[k].numel() else 0. for k in a}
    last=torch.load(fit.path/'models/iteration_000003.pt',map_location='cpu',weights_only=False)['splats']
    for k in b:assert torch.equal(b[k],last[k])
    first=torch.load(fit.path/'models/iteration_000000.pt',map_location='cpu',weights_only=False)['splats']
    assert any(not torch.equal(first[k],last[k]) for k in last)
    result=dict(status='passed',iterations=3,checkpoints=4,loss_rows=3,renders=3,
        rng_states_equal=True,last_snapshot_exactly_equals_final_model=True,
        independent_native_gs_max_parameter_differences=deltas)
    (out/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':main()
