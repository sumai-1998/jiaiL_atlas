"""Deletion is gated on successful verification and limited to run-owned intermediates."""
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image

from finish_rolling_benchmarks import prune_run


class RetentionTests(unittest.TestCase):
    def test_verified_cleanup_preserves_videos_metrics_and_existing_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'new';out.mkdir();report=root/'report';report.mkdir()
            baseline=root/'existing_baseline';baseline.mkdir();old=baseline/'keep.bin';old.write_bytes(b'untouched')
            scene='032dee9fb0a8';folder=out/scene;(folder/'gt').mkdir(parents=True)
            Image.new('RGB',(2,2)).save(folder/'gt/00000.png')
            (folder/'generated').mkdir();(folder/'generated/00000.png').write_bytes(b'png')
            (folder/'generated.mp4').write_bytes(b'video');(folder/'image_metrics.json').write_text('{}')
            (folder/'generation').mkdir();(folder/'generation/report.json').write_text('{"geometry_bridge_calls":[]}')
            (out/'plan.json').write_text(json.dumps(dict(method='map-ww-gs',method_label='F',
                parameters=dict(retention='compact: test'),inputs=[dict(scene_id=scene,baseline_scene_dir=str(baseline))])))
            (out/'verification.json').write_text('{"status":"failed"}')
            (report/'export_verification.json').write_text('{"status":"passed"}')
            with self.assertRaises(AssertionError):prune_run(out,report)
            self.assertTrue((folder/'generated/00000.png').exists())
            (out/'verification.json').write_text('{"status":"passed"}')
            prune_run(out,report)
            self.assertFalse((folder/'generated').exists());self.assertFalse((folder/'gt').exists())
            self.assertTrue((folder/'input.png').exists())
            self.assertEqual((folder/'generated.mp4').read_bytes(),b'video')
            self.assertTrue((folder/'image_metrics.json').exists());self.assertEqual(old.read_bytes(),b'untouched')
            self.assertTrue(json.loads((out/'retention_manifest.json').read_text())['verification_before_deletion'])


if __name__=='__main__':unittest.main()
