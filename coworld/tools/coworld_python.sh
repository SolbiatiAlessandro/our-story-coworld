#!/usr/bin/env bash
# Python with the pinned Coworld SDK available (same pin as tools/coworld.sh).
set -euo pipefail
exec uv run --no-project --python 3.12 --with 'coworld[auth] @ git+https://github.com/Metta-AI/coworld.git@9515332148d0c21a402f9c764e17b3e502835288' python "$@"
