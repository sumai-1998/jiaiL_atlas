"""Passive diagnostics for WorldWarp: never replaces its geometry or rendered hints."""
from pathlib import Path
import json
import numpy as np


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def verify_loaded_checkpoint(generator, out):
    import torch
    path = Path(generator.cfg.paths.finetuned_checkpoint_path).resolve()
    weights = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
    actual = generator.transformer.state_dict()
    missing, unexpected = sorted(set(actual)-set(weights)), sorted(set(weights)-set(actual))
    bad = []
    for key in set(weights) & set(actual):
        if weights[key].shape != actual[key].shape or not torch.equal(
                weights[key].to(dtype=actual[key].dtype), actual[key].detach().cpu()):
            bad.append(key)
    report = dict(path=str(path), tensor_count=len(actual), missing=missing,
                  unexpected=unexpected, differing=bad, passed=not (missing or unexpected or bad))
    dump(Path(out)/'checkpoint_audit.json', report)
    if not report['passed']:
        raise RuntimeError('Loaded transformer differs from fine-tuned checkpoint; see checkpoint_audit.json')


class GuidanceAudit:
    def __init__(self, root, model, warp):
        self.root = Path(root)
        self.root.mkdir()
        self.model, self.original_warp = model, warp
        self.original_inference = model.inference
        self.chunk = 0
        model.inference = self.inference

    def folder(self):
        p = self.root/f'chunk_{self.chunk:03d}'
        p.mkdir(exist_ok=True)
        return p

    def inference(self, *args, **kwargs):
        depth, poses, k = self.original_inference(*args, **kwargs)
        d = depth.detach().cpu().numpy()
        p = poses.detach().cpu().numpy()
        intr = k.detach().cpu().numpy()
        # Only first/last geometry depth is needed for this scale diagnostic.
        np.savez_compressed(self.folder()/'geometry.npz', c2w=p, intrinsics=intr,
                            depth_first_last=d[:, [0, -1]].astype('float16'),
                            depth_median=np.median(d, axis=(-1, -2)))
        return depth, poses, k

    def warp(self, source, target, video, poses, k, *args, **kwargs):
        import imageio.v2 as imageio
        from PIL import Image
        folder = self.folder()
        np.savez_compressed(folder/'request.npz', source_ids=source.cpu().numpy(),
                            target_ids=target.cpu().numpy(), c2w=poses.cpu().numpy(),
                            intrinsics=k.cpu().numpy())
        rgb, mask, corrected = self.original_warp(source, target, video, poses, k, *args, **kwargs)
        frames = (rgb[0].detach().clamp(0, 1).cpu().permute(0, 2, 3, 1).numpy()*255).astype('uint8')
        masks = mask[0].detach().float().cpu().numpy().reshape(len(frames), *frames.shape[1:3])
        with imageio.get_writer(folder/'warped.mp4', fps=30, codec='libx264', quality=9, macro_block_size=1) as writer:
            for frame in frames:
                writer.append_data(frame)
        for i in [0, 4, 12, 24, 36, 48]:
            Image.fromarray(frames[i]).save(folder/f'warped_{i:03d}.png')
            Image.fromarray((masks[i].clip(0, 1)*255).astype('uint8')).save(folder/f'mask_{i:03d}.png')
        dump(folder/'render.json', dict(chunk=self.chunk, shape=list(frames.shape),
              mask_mean=masks.mean(axis=(1, 2)).tolist(),
              valid_fraction=(masks >= .5).mean(axis=(1, 2)).tolist(),
              diagnostic_only=True, before_context_overwrite=True))
        return rgb, mask, corrected

    def close(self):
        self.model.inference = self.original_inference
