#!/usr/bin/env bash
set -euo pipefail

atlas_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
worldwarp_root="${atlas_root}/WorldWarp"
worldwarp_python="${GIL_WORLDWARP_PYTHON:-${atlas_root}/conda_envs/worldwarp/bin/python}"

export PYTHONNOUSERSITE=1
export HF_HOME="${atlas_root}/hf_cache"
export HF_HUB_CACHE="${HF_HOME}/hub"
export CUDA_HOME="${GIL_CUDA_WORLDWARP:-${CUDA_HOME:-/usr/local/cuda-12.8}}"
export PATH="${CUDA_HOME}/bin:${PATH}"
export LD_LIBRARY_PATH="${CUDA_HOME}/lib64:${LD_LIBRARY_PATH:-}"
export NO_PROXY="localhost,127.0.0.1,0.0.0.0,${NO_PROXY:-}"
export no_proxy="${NO_PROXY}"

cd "${worldwarp_root}"
exec "${worldwarp_python}" gradio_demo.py "$@"
