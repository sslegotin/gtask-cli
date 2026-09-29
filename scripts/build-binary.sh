#!/usr/bin/env bash
# Build a standalone gtask executable for THIS machine's OS and CPU.
# Output: dist/gtask. Needs the poetry env (poetry install) and a Python built
# with a shared libpython (pyenv: PYTHON_CONFIGURE_OPTS="--enable-shared";
# python.org and Homebrew builds are fine).
set -euo pipefail
cd "$(dirname "$0")/.."

poetry install --with bundle --quiet
poetry run pyinstaller \
  --onefile \
  --name gtask \
  --paths src \
  --clean \
  --noconfirm \
  --log-level WARN \
  src/gtask/__main__.py

echo "Built dist/gtask for $(uname -s) $(uname -m)"
echo "Recipients on macOS may need: xattr -d com.apple.quarantine gtask"
