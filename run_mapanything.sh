#!/usr/bin/env bash
set -euo pipefail
ATLAS_GEOM_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export HF_HOME="${ATLAS_GEOM_ROOT}/hf_cache"
export TORCH_HOME="${ATLAS_GEOM_ROOT}/.cache/torch_geometry"
export HF_HUB_DISABLE_TELEMETRY=1
export PYTHONNOUSERSITE=1
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-4}"
export TORCH_EXTENSIONS_DIR="${ATLAS_GEOM_ROOT}/.cache/torch_extensions_geometry"
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda-12.4}"
export CC="${CC:-${ATLAS_GEOM_ROOT}/conda_envs/game/bin/x86_64-conda-linux-gnu-gcc}"
export CXX="${CXX:-${ATLAS_GEOM_ROOT}/conda_envs/game/bin/x86_64-conda-linux-gnu-g++}"
export MAX_JOBS="${MAX_JOBS:-4}"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.6}"
export PYTHONPATH="${ATLAS_GEOM_ROOT}/MapAnything:${PYTHONPATH:-}"
exec "${GIL_MAPANYTHING_PYTHON:-${ATLAS_GEOM_ROOT}/conda_envs/mapanything/bin/python}" "${ATLAS_GEOM_ROOT}/scripts/infer_geometry.py" "$@"
