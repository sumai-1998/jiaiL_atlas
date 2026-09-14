#!/usr/bin/env python3
"""Download pinned MapAnything model snapshots; no login or license acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / "hf_cache"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
from huggingface_hub import snapshot_download
from safetensors import safe_open

MODELS = {
    "default": ("facebook/map-anything", "a1d87e9086706fb9974f3be5a3e3a0ca5401c5aa", "mapanything", "CC-BY-NC-4.0"),
    "apache": ("facebook/map-anything-apache", "00f9c245bbcb60522d1ed7f9e9d88462c6e3f38a", "mapanything-apache", "Apache-2.0"),
}
EXPECTED_SHA256 = {
    "default": "981f060c64664dff3272b5f5a823d350abe71a2f144444db4cfc325f3ed5a3a0",
    "apache": "fa06c0fdccefc5048e072c85935d5789b1e36b307f3859033c17f9dcb9fd5201",
}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--variant",choices=["default","apache","all"],default="all")
    args=parser.parse_args()
    chosen=MODELS if args.variant=="all" else {args.variant:MODELS[args.variant]}
    for variant,(repo,revision,name,license_name) in chosen.items():
        dest=ROOT/"checkpoints"/name
        print(f"Downloading {repo} @ {revision} to {dest}",flush=True)
        snapshot_download(repo_id=repo,revision=revision,local_dir=dest,max_workers=2)
        ckpt=dest/"model.safetensors"
        assert ckpt.stat().st_size==4914062480, (ckpt,ckpt.stat().st_size)
        with safe_open(ckpt,framework="pt",device="cpu") as handle:
            keys=list(handle.keys())
            shapes={key:handle.get_slice(key).get_shape() for key in keys}
        digest=hashlib.sha256()
        with ckpt.open("rb") as handle:
            for block in iter(lambda:handle.read(16*1024*1024),b""):
                digest.update(block)
        assert digest.hexdigest()==EXPECTED_SHA256[variant], "Checkpoint SHA256 does not match official HF LFS object"
        record=dict(repo_id=repo,revision=revision,license=license_name,checkpoint=str(ckpt),
                    size_bytes=ckpt.stat().st_size,sha256=digest.hexdigest(),tensor_count=len(keys),
                    tensor_shapes=shapes)
        (dest/"local_manifest.json").write_text(json.dumps(record,ensure_ascii=False,indent=2))
        print(f"VERIFIED {variant}: {len(keys)} tensors, {record['size_bytes']} bytes, SHA256={record['sha256']}",flush=True)

if __name__=="__main__":main()
