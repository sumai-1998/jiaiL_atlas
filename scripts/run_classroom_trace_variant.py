#!/usr/bin/env python3
"""Run a classroom variant with opt-in exhaustive geometry tracing."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'WorldWarp'))


def main():
    p=argparse.ArgumentParser(add_help=False)
    p.add_argument('--trace-variant',choices=('original','rolling_gs','anchor_gs','anchor_points','game'),required=True)
    p.add_argument('--trace-root',type=Path,required=True)
    p.add_argument('--trace-baseline',type=Path,help='Portable reference or historical baseline for original A captions')
    args,rest=p.parse_known_args()
    import classroom_geometry_trace as trace
    trace.initialize(args.trace_root)
    os.environ['CLASSROOM_CAPTURE_MAP_NATIVE']='1'
    if args.trace_variant=='game':
        sys.path.insert(0,str(ROOT/'GaME'))
        trace.install_game()
        import fuse_geometry_game as runner
    else:
        import pose_control as pc
        trace.install_worldwarp()
        if args.trace_variant=='original':
            import generate_worldwarp_rotation as runner
            from pipeline_reference import reference_captions
            baseline=args.trace_baseline or ROOT/'WorldWarp_outputs/classroom_pan_left_2026-09-07'
            captions=reference_captions(baseline)
            original=pc.WanVideoGenerator
            instances=[]
            class RecordedOriginal(original):
                def __init__(self,*a,**kw):
                    super().__init__(*a,**kw);instances.append(self)
                def _init_captioner(self,**kw):
                    self.caption_model='cached_original_captions'
                def get_caption(self,**kw):
                    return captions[self.trace_chunk]
                def run_inference_chunk(self,chunk_idx,*a,**kw):
                    self.trace_chunk=chunk_idx
                    return super().run_inference_chunk(chunk_idx,*a,**kw)
            pc.WanVideoGenerator=RecordedOriginal
        else:
            import generate_worldwarp_mapanything as runner
            rest=['--variant',args.trace_variant]+rest
    sys.argv=[sys.argv[0]]+rest
    runner.main()
    if args.trace_variant=='original':
        # The normal loop estimates geometry for the input to each chunk. The
        # final generated chunk has no successor, so capture its TTT3R output too.
        import torch
        generator=instances[0]
        output=Path(generator.cfg.experiment.output_root).parent
        report=json.loads((output/'report.json').read_text())
        last=report['completed_chunks'][-1]['path']
        trace.set_chunk(4)
        video=pc.preprocess_video_from_path(last,608,480)[None].to(generator.device)
        with torch.no_grad():
            generator.ttt3r.inference(video,reset_interval=1000000)
        del video
        (trace.ROOT/'ttt3r_all_generated_frames_mapping.json').write_text(json.dumps(dict(
            frames=321,note='Chunk 0 TTT3R observes repeated input. Chunks 1-4 cover all generated frames; chunk 4 is diagnostic only.',
            sources=[dict(trace_chunk=i,global_start=(i-1)*80,local_start=0 if i==1 else 1,
                          local_end_inclusive=80) for i in range(1,5)]),indent=2))
    trace.flush()
    trace.write_json(trace.ROOT/'capture_complete.json',dict(status='complete',variant=args.trace_variant,
        fits=[dict(path=str(f.path),iterations=f.steps) for f in trace.FITS]))


if __name__=='__main__':main()
