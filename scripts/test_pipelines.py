"""CPU tests for routing, actual adapter arguments, reference data and run status."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parent))
import pipelines as cli
from pipeline_reference import reference_captions


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.image=self.root/'different scene.png'
        from PIL import Image
        Image.new('RGB',(100,150),(32,84,123)).save(self.image)

    def args(self,name='G',*extra):
        return cli.parser().parse_args(['plan','--pipeline',name,'--input',str(self.image),'--output',str(self.root/'result'),*extra])

    def test_every_pipeline_routes_without_old_runs(self):
        for pipeline in cli.REGISTRY['pipelines']:
            with self.subTest(pipeline=pipeline['id']):
                plan=cli.build_plan(self.args(pipeline['id']))
                self.assertFalse((self.root/'result').exists())
                text=json.dumps(plan)
                self.assertNotIn('classroom_pan_left_2026',text)
                self.assertNotIn('WorldWarp_outputs',text)
                self.assertTrue(all(Path(x['command'][2]).is_file() for x in plan['steps']))
                if pipeline['kind']=='video':self.assertEqual(plan['video_contract']['delivered_frames'],321)

    def test_historical_context_and_strength_are_preserved(self):
        # Checked against each old artifacts/*/config.yaml, not inferred from
        # neighboring experiment labels: D/E kept context=1, unlike C.
        expected={'A':(1,.6),'B':(1,.6),'C':(5,.6),'D':(1,.5),'E':(1,.65),
                  'F':(5,.6),'G':(5,.6),'H':(5,.6)}
        for name,(context,strength) in expected.items():
            plan=cli.build_plan(self.args(name))
            self.assertEqual((plan['parameters']['context_frames'],plan['parameters']['strength']),(context,strength))

    def test_commands_match_real_argument_parsers(self):
        def flags(filename):
            result=set()
            for node in ast.walk(ast.parse((cli.ROOT/'scripts'/filename).read_text())):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='add_argument':
                    for arg in node.args:
                        if isinstance(arg,ast.Constant) and isinstance(arg.value,str) and arg.value.startswith('--'):result.add(arg.value)
            return result
        common=flags('generate_worldwarp_rotation.py')
        for name in [p['id'] for p in cli.REGISTRY['pipelines']]+['A','F','G','H']:
            full=name in ['A','F','G','H']
            options=['--capture','full'] if full else []
            if name in ['F','G','H']:options+=['--posthoc']
            plan=cli.build_plan(self.args(name,*options))
            for step in plan['steps']:
                script=Path(step['command'][2]).name
                allowed=flags(script)
                if script in ['generate_worldwarp_mapanything.py','generate_worldwarp_hybrid_context.py','run_classroom_trace_variant.py']:allowed |= common
                if script=='run_classroom_trace_variant.py':allowed |= flags('generate_worldwarp_mapanything.py')
                used={x for x in step['command'][3:] if x.startswith('--')}
                self.assertFalse(used-allowed,(name,script,used-allowed))

    def test_boundaries_and_invalid_requests(self):
        for options in [('--chunks','16'),('--strength','nan'),('--strength','1.1'),('--context-frames','4'),('--map-variant','apache')]:
            with self.subTest(options=options),self.assertRaises(ValueError):cli.build_plan(self.args('G',*options))
        with self.assertRaises(ValueError):cli.build_plan(self.args('A','--context-frames','5'))
        with self.assertRaises(ValueError):cli.build_plan(self.args('C','--capture','full'))
        with self.assertRaises(ValueError):cli.build_plan(self.args('A','--posthoc'))
        (self.root/'result').mkdir()
        with self.assertRaises(FileExistsError):cli.build_plan(self.args())

    def test_new_reference_uses_this_image_and_caption(self):
        import numpy as np
        from PIL import Image,ImageOps
        caption=self.root/'caption.txt';caption.write_text('A different scene; preserve its contents.')
        reference=self.root/'reference'
        subprocess.run([sys.executable,str(cli.ROOT/'scripts/pipeline_reference.py'),'--image',str(self.image),
                        '--output',str(reference),'--caption-file',str(caption),'--total-angle-deg','-12'],check=True,stdout=subprocess.DEVNULL)
        wanted=ImageOps.fit(Image.open(self.image).convert('RGB'),(480,608),method=Image.Resampling.LANCZOS)
        np.testing.assert_array_equal(np.array(wanted),np.array(Image.open(reference/'input_prepared.png')))
        with np.load(reference/'requested_camera_trajectory.npz') as trajectory:
            self.assertEqual(trajectory['c2w'].shape,(321,4,4))
            np.testing.assert_array_equal(trajectory['c2w'][:,:3,3],0)
            yaw=np.rad2deg(np.arctan2(trajectory['c2w'][:,0,2],trajectory['c2w'][:,0,0]))
            np.testing.assert_allclose(yaw,np.linspace(0,-12,321),atol=2e-6)
        self.assertEqual(reference_captions(reference),[caption.read_text()]*4)
        # A reference remains usable after moving it to another path.
        moved=self.root/'moved';reference.rename(moved)
        self.assertEqual(reference_captions(moved),[caption.read_text()]*4)

    def test_runtime_success_and_failure_are_recorded(self):
        for code in [0,7]:
            with self.subTest(code=code):
                args=self.args('G','--gpu','1');args.output=str(self.root/f'run_{code}')
                plan=cli.build_plan(args)
                plan['steps']=[dict(name='fake_adapter',environment='worldwarp',command=[sys.executable,'-c',f'print("adapter log");raise SystemExit({code})'])]
                with mock.patch.object(cli,'preflight',return_value=[dict(ok=True)]),mock.patch.object(cli,'verify_outputs',return_value={'checked':True}),contextlib.redirect_stdout(io.StringIO()):
                    result=cli.run(plan)
                report=json.loads((Path(args.output)/'status.json').read_text())
                self.assertEqual(report['status'],'complete' if code==0 else 'failed')
                self.assertEqual(result,0 if code==0 else 1)
                self.assertIn('adapter log',(Path(args.output)/'logs/fake_adapter.log').read_text())

    def test_preflight_failure_does_not_create_run(self):
        plan=cli.build_plan(self.args('G','--gpu','1'))
        with mock.patch.object(cli,'preflight',return_value=[dict(check='missing',ok=False)]),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.run(plan),2)
        self.assertFalse(Path(plan['output']).exists())

    def test_paths_with_shell_metacharacters_are_plain_arguments(self):
        prompt='Preserve $HOME; $(do_not_execute) and `literal`.'
        plan=cli.build_plan(self.args('G','--prompt',prompt))
        command=plan['steps'][-1]['command']
        self.assertEqual(command[command.index('--prompt')+1],prompt)
        self.assertEqual(command[command.index('--image')+1],str(self.image))


if __name__=='__main__':unittest.main()
