"""Portable camera/caption reference preparation; does not run a video model."""
import argparse
import json
from pathlib import Path


def reference_captions(reference, chunks=4):
    """Read new portable references and legacy baseline reports."""
    reference = Path(reference).resolve()
    if (reference/'reference.json').exists():
        return [(reference/'captions'/f'chunk_{i:03d}.txt').read_text() for i in range(chunks)]
    report = json.loads((reference/'report.json').read_text())
    artifact = Path(report['completed_chunks'][0]['path']).parent.parent
    if not artifact.is_absolute():
        artifact = reference/artifact
    if not artifact.exists():
        matches = sorted((reference/'artifacts').glob('*/captions'))
        if len(matches) != 1:
            raise FileNotFoundError('Cannot locate baseline captions; use a portable reference or an intact baseline')
        artifact = matches[0].parent
    return [(artifact/'captions'/f'chunk_{i:03d}.txt').read_text() for i in range(chunks)]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--caption-file',required=True,type=Path)
    p.add_argument('--chunks',type=int,default=4)
    p.add_argument('--total-angle-deg',type=float,default=-20)
    a=p.parse_args()
    if a.chunks<1 or not -90<a.total_angle_deg<0: p.error('Positive chunks and -90 < angle < 0 required')
    import numpy as np
    from PIL import Image,ImageOps
    from generate_worldwarp_rotation import constant_y_rotation
    a.output.mkdir(parents=True,exist_ok=False)
    with Image.open(a.image) as image:
        prepared=ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),(480,608),method=Image.Resampling.LANCZOS)
        prepared.save(a.output/'input_prepared.png')
    count=80*a.chunks+1
    poses=constant_y_rotation(count,a.total_angle_deg)
    k=np.array([[576,0,240],[0,576,304],[0,0,1]],dtype=np.float32)
    np.savez_compressed(a.output/'requested_camera_trajectory.npz',c2w=poses,intrinsics=np.repeat(k[None],count,axis=0),fps=30)
    caption=a.caption_file.read_text().strip()
    if not caption: raise ValueError('Caption must not be empty')
    (a.output/'captions').mkdir()
    for i in range(a.chunks): (a.output/'captions'/f'chunk_{i:03d}.txt').write_text(caption)
    metadata=dict(kind='prepared_camera_and_text_reference',generated_video=False,input=str(a.image.resolve()),chunks=a.chunks,frames=count,fps=30,seconds=count/30,width=480,height=608,total_angle_deg=a.total_angle_deg,captions='captions/chunk_NNN.txt')
    (a.output/'reference.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata,indent=2))


if __name__=='__main__': main()
