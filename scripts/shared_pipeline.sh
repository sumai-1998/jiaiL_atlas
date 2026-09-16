#!/usr/bin/env bash
# Run the shared installation while keeping runtime caches in the caller's area.
set -euo pipefail

gil_repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
export GIL_WORLDWARP_PYTHON="${GIL_WORLDWARP_PYTHON:-$gil_repo_root/conda_envs/worldwarp/bin/python}"
export GIL_MAPANYTHING_PYTHON="${GIL_MAPANYTHING_PYTHON:-$gil_repo_root/conda_envs/mapanything/bin/python}"
export GIL_GAME_PYTHON="${GIL_GAME_PYTHON:-$gil_repo_root/conda_envs/game/bin/python}"
export GIL_RUNTIME_CACHE="${GIL_RUNTIME_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/gil_atlas}"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1

if [[ ! -x "$GIL_WORLDWARP_PYTHON" ]]; then
    printf 'Cannot execute shared Python: %s\n' "$GIL_WORLDWARP_PYTHON" >&2
    exit 1
fi

# Preserve caller cwd: relative --input and --output paths belong to the caller.
exec "$GIL_WORLDWARP_PYTHON" "$gil_repo_root/scripts/pipelines.py" "$@"
