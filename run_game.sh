#!/usr/bin/env bash
set -euo pipefail
ATLAS_GEOM_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export TORCH_HOME="${ATLAS_GEOM_ROOT}/.cache/torch_geometry"
export HF_HOME="${ATLAS_GEOM_ROOT}/hf_cache"
export PYTHONNOUSERSITE=1
export WANDB_MODE=disabled
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-4}"
exec "${GIL_GAME_PYTHON:-${ATLAS_GEOM_ROOT}/conda_envs/game/bin/python}" "${ATLAS_GEOM_ROOT}/scripts/fuse_geometry_game.py" "$@"
