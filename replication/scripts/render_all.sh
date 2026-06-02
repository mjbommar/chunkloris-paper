#!/usr/bin/env bash
# Regenerate every figure from data/*.json, then rebuild the paper.
#
# Run from the project root:
#   bash projects/asgi-perchunk-survey/scripts/render_all.sh
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJ_DIR="$( cd "${SCRIPT_DIR}/.." && pwd )"

cd "${SCRIPT_DIR}"

echo "==> rendering figures"
for s in render_*.py; do
    echo "==> ${s}"
    uv run --with matplotlib --with numpy --with seaborn python "${s}"
done

echo
echo "==> figures generated:"
ls -la "${PROJ_DIR}/figures/"

echo
echo "==> rebuilding paper"
cd "${PROJ_DIR}/paper"
make clean >/dev/null 2>&1 || true
make

echo
echo "==> done."
echo "    paper -> ${PROJ_DIR}/paper/main.pdf"
echo "    figures -> ${PROJ_DIR}/figures/"
