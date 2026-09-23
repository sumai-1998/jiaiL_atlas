import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import torch

from worldwarp_benchmark_audit import verify_loaded_checkpoint


class CheckpointAuditTests(unittest.TestCase):
    def test_exact_dtype_cast_is_accepted_and_missing_weights_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'weights.pt'
            layer=torch.nn.Linear(2,2).to(torch.bfloat16)
            weights={k:v.float() for k,v in layer.state_dict().items()}
            torch.save(weights,path)
            generator=SimpleNamespace(transformer=layer,
                cfg=SimpleNamespace(paths=SimpleNamespace(finetuned_checkpoint_path=str(path))))
            verify_loaded_checkpoint(generator,root)
            self.assertTrue(json.loads((root/'checkpoint_audit.json').read_text())['passed'])
            weights.pop('bias');torch.save(weights,path)
            with self.assertRaises(RuntimeError):verify_loaded_checkpoint(generator,root)
            report=json.loads((root/'checkpoint_audit.json').read_text())
            self.assertEqual(report['missing'],['bias'])

    def test_same_shapes_but_unloaded_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'weights.pt'
            layer=torch.nn.Linear(2,2)
            weights={k:v.clone()+1 for k,v in layer.state_dict().items()}
            torch.save(weights,path)
            generator=SimpleNamespace(transformer=layer,
                cfg=SimpleNamespace(paths=SimpleNamespace(finetuned_checkpoint_path=str(path))))
            with self.assertRaises(RuntimeError):verify_loaded_checkpoint(generator,root)
            self.assertEqual(set(json.loads((root/'checkpoint_audit.json').read_text())['differing']),{'weight','bias'})


if __name__=='__main__':unittest.main()
