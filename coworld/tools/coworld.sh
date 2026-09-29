#!/usr/bin/env bash
# The Coworld CLI, pinned to the commit the Stardew coworld certified with.
set -euo pipefail
exec uvx --from 'coworld[auth] @ git+https://github.com/Metta-AI/coworld.git@9515332148d0c21a402f9c764e17b3e502835288' coworld "$@"
