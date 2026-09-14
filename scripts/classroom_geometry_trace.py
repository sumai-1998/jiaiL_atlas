"""Opt-in, lossless geometry recording without changing upstream source files.

Functions are instrumented in this process only. Model arithmetic and random
sampling remain the upstream implementation; the hooks copy detached tensors.
"""
import ast
import atexit
import inspect
import json
import os
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = None
CHUNK = None
FITS = []
PENDING = []
EXECUTOR = None


def initialize(root):
    global ROOT, EXECUTOR
    ROOT = Path(root).resolve()
    ROOT.mkdir(parents=True, exist_ok=True)
    EXECUTOR = ThreadPoolExecutor(max_workers=1)
    atexit.register(flush)


def cpu(value):
    import torch
    if torch.is_tensor(value):
        return value.detach().to('cpu', copy=True)
    if isinstance(value, dict):
        return {k: cpu(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(cpu(v) for v in value)
    return value


def array(value):
    import numpy as np
    import torch
    if torch.is_tensor(value):
        value = value.detach().cpu()
        if value.dtype == torch.bfloat16:
            value = value.float()
        return value.numpy().copy()
    return np.asarray(value).copy()


def submit(fn, *args):
    # Bounded queue: no unlimited retention of model snapshots in host RAM.
    while len(PENDING) >= 2:
        PENDING.pop(0).result()
    PENDING.append(EXECUTOR.submit(fn, *args))


def flush():
    while PENDING:
        PENDING.pop(0).result()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def save_npz(path, values):
    import numpy as np
    np.savez_compressed(path, **values)


def rgb_png(path, rgb):
    import numpy as np
    from PIL import Image
    Image.fromarray(np.rint(np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(path)


def scalar_preview(path, data, positive=False):
    import cv2
    import numpy as np
    from PIL import Image
    data = np.squeeze(data)
    valid = np.isfinite(data)
    if positive:
        valid &= data > 0
    lo, hi = np.percentile(data[valid], [2, 98]) if valid.any() else (0., 1.)
    norm = np.zeros(data.shape, np.float32)
    norm[valid] = np.clip((data[valid] - lo) / max(float(hi-lo), 1e-8), 0, 1)
    color = cv2.applyColorMap((norm*255).astype(np.uint8), cv2.COLORMAP_TURBO)[..., ::-1]
    color[~valid] = 0
    Image.fromarray(color).save(path)
    return [float(lo), float(hi)]


def set_chunk(chunk):
    global CHUNK
    CHUNK = int(chunk)


def chunk_dir():
    p = ROOT / (f'chunk_{CHUNK:03d}' if CHUNK is not None else 'game')
    p.mkdir(parents=True, exist_ok=True)
    return p


class Fit:
    def __init__(self, local, kind):
        self.kind = kind
        self.steps = 0
        parent = chunk_dir()
        idx = sum(f.path.parent == parent for f in FITS)
        self.path = parent / f'{kind}_fit_{idx:02d}'
        self.path.mkdir(exist_ok=False)
        for name in ('models', 'training_renders', 'training_rgb'):
            (self.path/name).mkdir()
        self.expected = int(local['num_iterations' if kind == 'native_gs' else 'iterations'])
        self.losses = (self.path/'losses.jsonl').open('w', buffering=1)
        if kind == 'native_gs':
            save_npz(self.path/'training_inputs.npz', {k: array(local[k]) for k in
                ('video_tensor', 'depth_maps', 'camera_poses', 'intrinsics', 'source_ids')})
        else:
            import torch
            torch.save(cpu(local['self'].keyframes), self.path/'training_keyframes.pt')
        FITS.append(self)
        self.save_model(local, 0)
        write_json(self.path/'manifest.json', dict(status='running', kind=kind,
            expected_iterations=self.expected, checkpoint_0='Before the first update',
            render_alignment='Iteration n training render and loss use model n-1; model n is after its update.',
            model_scope='All model tensors at every step; optimizer states additionally saved at the end.',
            rendered_view='The exact source view sampled by the optimizer, recorded in every loss row.'))

    def save_model(self, local, step):
        import torch
        if self.kind == 'native_gs':
            state = dict(splats=cpu(local['splats']), pose_delta=cpu(local.get('pose_delta')))
        else:
            model = local['self'].gaussian_model
            state = dict(tensors={k: cpu(v) for k,v in vars(model).items() if torch.is_tensor(v)},
                active_sh_degree=model.active_sh_degree, spatial_lr_scale=model.spatial_lr_scale)
        state.update(iteration=step, phase='initial' if step == 0 else 'after_update', kind=self.kind)
        submit(torch.save, state, self.path/'models'/f'iteration_{step:06d}.pt')

    def record(self, local):
        import numpy as np
        step = int(local['iteration']) + 1
        if step != self.steps + 1:
            raise RuntimeError('Non-contiguous trace iterations')
        self.save_model(local, step)
        if self.kind == 'native_gs':
            values = dict(rgb=array(local['colors'])[0], alpha=array(local['alphas'])[0],
                c2w=array(local['camtoworld'])[0], intrinsics=array(local['K'])[0])
            if local['depths'] is not None:
                values['depth_z'] = array(local['depths'])[0]
            losses = {k: float(local[k].detach()) for k in ('loss', 'l1loss', 'ssimloss', 'depthloss') if k in local}
            row = dict(iteration=step, source_view_id=int(local['view_id']), **losses,
                ssim_lambda=float(local['ssim_lambda']), depth_lambda=float(local['depth_lambda']))
        else:
            values = dict(rgb=array(local['image']).transpose(1,2,0), depth_z=array(local['depth']),
                alpha=array(local['_trace_alpha']), loss_mask=array(local['mask']),
                w2c=array(local['pose']), intrinsics=array(local['intrinsics']))
            row = dict(iteration=step, source_view_id=int(local['keyframe_id']),
                **{k: float(local[k].detach()) for k in ('total_loss','color_loss','depth_loss','reg_loss')})
        row.update(render_model_iteration=step-1, checkpoint_after_iteration=step)
        if not all(np.isfinite(v) for k,v in row.items() if isinstance(v, float)):
            raise RuntimeError(f'Non-finite loss: {row}')
        self.losses.write(json.dumps(row)+'\n')
        submit(save_npz, self.path/'training_renders'/f'iteration_{step:06d}.npz', values)
        submit(rgb_png, self.path/'training_rgb'/f'iteration_{step:06d}.png', values['rgb'])
        self.steps = step

    def finish(self, local):
        import torch
        if self.steps != self.expected:
            raise RuntimeError(f'Missing iterations at {self.path}: {self.steps}/{self.expected}')
        if self.kind == 'native_gs':
            state = {k: cpu(v.state_dict()) for k,v in local['optimizers'].items()}
        else:
            state = cpu(local['self'].gaussian_model.optimizer.state_dict())
        submit(torch.save, state, self.path/'final_optimizer_states.pt')
        flush()
        self.losses.close()
        p=self.path/'manifest.json'; data=json.loads(p.read_text())
        data.update(status='complete', iterations=self.steps, model_snapshots=self.steps+1,
            training_renders=self.steps, loss_rows=self.steps)
        write_json(p,data)


def save_ttt(local):
    import numpy as np
    import torch
    path=chunk_dir()/'ttt3r'
    path.mkdir(exist_ok=False)
    depth, poses, ks = (array(local[k])[0] for k in ('depths','poses','intrins'))
    rgb = array(local['video_batch'])[0].transpose(0,2,3,1)
    for name, data in (('depth_z',depth),('predicted_c2w',poses),('predicted_intrinsics',ks)):
        np.save(path/f'{name}.npy',data)
    views=local['outputs']['views']
    reset=[bool(v['reset'][0]) for v in views]
    keep=[True]+[not x for x in reset[:-1]]
    preds=[p for p,k in zip(local['outputs']['pred'],keep) if k]
    if len(preds) != len(depth):
        raise RuntimeError('TTT3R raw/frame count mismatch')
    (path/'frames').mkdir(); (path/'native_predictions').mkdir(); (path/'depth_preview').mkdir()
    for i in range(len(depth)):
        submit(torch.save,cpu(preds[i]),path/'native_predictions'/f'frame_{i:03d}.pt')
        submit(save_npz,path/'frames'/f'frame_{i:03d}.npz',dict(rgb=rgb[i],depth_z=depth[i],
            predicted_c2w=poses[i],predicted_intrinsics=ks[i]))
        submit(scalar_preview,path/'depth_preview'/f'frame_{i:03d}.png',depth[i],True)
    flush()
    write_json(path/'manifest.json',dict(status='complete',frames=len(depth),
        chunk=CHUNK, reset_interval=local['reset_interval'],
        note='Every frame passed to TTT3R, including the repeated conditioning image in chunk 0. Predicted cameras are distinct from requested cameras.'))


def save_condition(local):
    import numpy as np
    from PIL import Image
    path=chunk_dir()/'diffusion_condition'
    path.mkdir(exist_ok=False)
    rgb=array(local['warped'])[0].transpose(0,2,3,1)
    mask=array(local['valid_masks'])[0,:,0]
    latent_mask=array(local['valid_masks_lat'])
    np.save(path/'rgb_float32.npy',rgb)
    np.save(path/'binary_mask.npy',mask)
    np.save(path/'latent_mask.npy',latent_mask)
    save_npz(path/'camera_request.npz',{k:array(local[k]) for k in
        ('source_ids','target_ids','rel_poses','chunk_intrinsics')})
    (path/'rgb').mkdir(); (path/'mask').mkdir()
    for i in range(len(rgb)):
        submit(rgb_png,path/'rgb'/f'frame_{i:03d}.png',rgb[i])
        Image.fromarray((mask[i]*255).astype(np.uint8)).save(path/'mask'/f'frame_{i:03d}.png')
    flush()
    write_json(path/'manifest.json',dict(status='complete',frames=len(rgb),context_frames=local['context_frames'],
        note='Exact RGB after context replacement and clamp, immediately before VAE encoding; binary and final latent-space masks saved.'))


def save_warp(local):
    import numpy as np
    path=chunk_dir()/'raw_geometry_warp'
    path.mkdir(exist_ok=False)
    rgb=array(local['warped']); alpha=array(local['valid_masks'])
    np.save(path/'rgb.npy',rgb); np.save(path/'alpha.npy',alpha)
    write_json(path/'manifest.json',dict(status='complete',frames=int(rgb.shape[1]),
        note='Raw geometry return, before RGB clamp, alpha threshold and context replacement.'))


def save_frames(local):
    import numpy as np
    from PIL import Image
    path=chunk_dir()/'generated_frames_before_codec'
    path.mkdir(exist_ok=False)
    frames=local['frames']
    for i, frame in enumerate(frames):
        Image.fromarray(frame).save(path/f'frame_{i:03d}.png')
    write_json(path/'manifest.json',dict(status='complete',frames=len(frames),
        note='Exact uint8 frames before MP4 encoding, including context prefix.'))


def _statements(code):
    return ast.parse(code).body


def instrument(owner, name, module, transform):
    original=getattr(owner,name)
    tree=ast.parse(textwrap.dedent(inspect.getsource(original)))
    node=tree.body[0]
    node.name='_classroom_traced_'+name
    transform(node)
    ast.fix_missing_locations(tree)
    module.__dict__['_classroom_trace']=sys.modules[__name__]
    source=ast.unparse(tree)
    dest=ROOT/'instrumented_sources';dest.mkdir(exist_ok=True)
    (dest/f'{owner.__name__}_{name}.py').write_text(source+'\n')
    exec(compile(tree,str(dest/f'{owner.__name__}_{name}.py'),'exec'),module.__dict__)
    setattr(owner,name,module.__dict__.pop(node.name))


def _fit_transform(node, kind):
    for i,stmt in enumerate(node.body):
        if isinstance(stmt,ast.For) and isinstance(stmt.target,ast.Name) and stmt.target.id=='iteration':
            node.body[i:i]=_statements(f"_trace_fit = _classroom_trace.Fit(locals(), '{kind}')")
            stmt.body.extend(_statements('_trace_fit.record(locals())'))
            node.body[i+2:i+2]=_statements('_trace_fit.finish(locals())')
            if kind=='game_gs':
                for j,child in enumerate(stmt.body):
                    if isinstance(child,ast.Delete) and any(isinstance(t,ast.Name) and t.id=='render_pkg' for t in child.targets):
                        stmt.body[j:j]=_statements("_trace_alpha = render_pkg['alpha'].detach()")
                        break
                else: raise RuntimeError('GaME render hook missing')
            break
    else: raise RuntimeError('GS iteration loop not found')


def install_worldwarp():
    import pose_control as pc
    import src.ttt3r.ttt3r as gs
    instrument(gs.GS3DWarper,'_train_splats',gs,lambda n:_fit_transform(n,'native_gs'))
    def ttt_transform(node):
        for i,stmt in enumerate(node.body):
            if isinstance(stmt,ast.Return):
                node.body[i:i]=_statements('_classroom_trace.save_ttt(locals())');break
        else: raise RuntimeError('TTT return missing')
    instrument(gs.TTT3RInference,'inference',gs,ttt_transform)
    def run_transform(node):
        node.body[0:0]=_statements('_classroom_trace.set_chunk(chunk_idx)')
        class Inject(ast.NodeTransformer):
            def visit_Assign(self,stmt):
                names={x.id for x in stmt.targets if isinstance(x,ast.Name)}
                if 'warped_lat' in names:
                    return _statements('_classroom_trace.save_condition(locals())')+[stmt]
                if 'warped' in names and isinstance(stmt.value,ast.Call) and isinstance(stmt.value.func,ast.Attribute) and stmt.value.func.attr=='clamp':
                    return _statements('_classroom_trace.save_warp(locals())')+[stmt]
                return stmt
            def visit_Expr(self,stmt):
                if isinstance(stmt.value,ast.Call) and isinstance(stmt.value.func,ast.Attribute) and stmt.value.func.attr=='mimsave':
                    return _statements('_classroom_trace.save_frames(locals())')+[stmt]
                return stmt
        Inject().visit(node)
    instrument(pc.WanVideoGenerator,'run_inference_chunk',pc,run_transform)


def install_game():
    import src.entities.game as game
    instrument(game.GaME,'optimize_model',game,lambda n:_fit_transform(n,'game_gs'))


def save_map_native(output, predictions, views, frame_ids):
    """Save every raw MapAnything view before any spatial resampling."""
    import numpy as np
    import torch
    path=Path(output).parent/'mapanything_native'
    path.mkdir(parents=True,exist_ok=False)
    rows=[]
    for i,(pred,view,frame_id) in enumerate(zip(predictions,views,frame_ids)):
        item=path/f'view_{i:03d}_global_{int(frame_id):03d}';item.mkdir()
        torch.save(cpu(pred),item/'prediction.pt')
        torch.save(cpu(view),item/'processed_input.pt')
        values={k:array(v) for k,v in pred.items() if torch.is_tensor(v)}
        np.savez_compressed(item/'prediction_arrays.npz',**values)
        scales={}
        for key,positive in (('depth_z',True),('conf',False)):
            if key in values:
                scales[key]=scalar_preview(item/f'{key}.png',values[key],positive)
        write_json(item/'metadata.json',dict(source_index=i,global_frame=int(frame_id),
            fields={k:dict(shape=list(v.shape),dtype=str(v.dtype)) for k,v in values.items()},preview_percentile_2_98=scales))
        rows.append(dict(index=i,global_frame=int(frame_id),directory=str(item)))
    write_json(path/'manifest.json',dict(status='complete',views=len(rows),frames=rows,
        note='Native model outputs BEFORE camera-coordinate resampling. PT preserves tensor dtypes; NPZ casts BF16 to exact FP32 values.'))
