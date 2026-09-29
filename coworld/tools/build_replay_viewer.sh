#!/usr/bin/env bash
# Called by `coworld build` with the absolute bundle directory as $1.
set -euo pipefail

package_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${1:?usage: build_replay_viewer.sh <output-dir>}"
if [[ "${output_dir}" != /* || "${output_dir}" == "/" || "${output_dir}" == "${package_dir}" ]]; then
  echo "unsafe bundle output: ${output_dir}" >&2
  exit 1
fi

rm -rf "${output_dir}"
mkdir -p "${output_dir}"
cp "${package_dir}/ourstory/game/client/viewer.html" "${output_dir}/index.html"
