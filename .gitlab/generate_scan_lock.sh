#!/bin/sh
# Maintenance only: generate a real pip-compile input for the dependency scanner.
set -eu
cd "$(dirname "$0")/.."
python3 - <<'PY'
import sys
if sys.platform != 'linux' or sys.version_info[:2] != (3, 12):
    raise SystemExit('Run this maintenance command in the pinned Linux/Python 3.12 SDK container')
PY
mkdir -p out/dependency-lock
lock_stage=$(mktemp -d "$PWD/out/dependency-lock/session.XXXXXXXX")
trap 'rm -rf -- "$lock_stage"' EXIT
trap 'exit 1' HUP INT TERM
export PYTHONDONTWRITEBYTECODE=1 TMPDIR="$lock_stage/tmp"
export PIP_CACHE_DIR="$lock_stage/pip-cache" XDG_CACHE_HOME="$lock_stage/cache"
mkdir -p "$TMPDIR"
export PIP_CONFIG_FILE=/dev/null PIP_INDEX_URL=https://pypi.org/simple PIP_EXTRA_INDEX_URL= PIP_NO_INDEX=0
python3 .gitlab/check_dependency_coverage.py --write-input "$lock_stage/requirements.in"
# The SDK's Python strips pip; bootstrap only into this disposable session.
pip_bootstrap=/usr/share/python-wheels/pip-24.0-py3-none-any.whl
test -f "$pip_bootstrap"
PYTHONPATH="$pip_bootstrap" python3 -m pip install --target "$lock_stage/tools" \
  --only-binary :all: --no-cache-dir --quiet pip-tools==7.6.2 pip==26.3
export PYTHONPATH="$lock_stage/tools"
python3 - <<'PY'
from importlib.metadata import version
assert version('pip') == '26.3' and version('pip-tools') == '7.6.2'
PY
python3 -m piptools compile --cache-dir "$lock_stage/pip-tools-cache" \
  --allow-unsafe --strip-extras --no-emit-index-url \
  --no-emit-trusted-host --no-header --no-annotate \
  --output-file "$lock_stage/resolved.txt" "$lock_stage/requirements.in"
python3 .gitlab/generate_scan_lock.py --resolved "$lock_stage/resolved.txt" \
  --output .gitlab/pipcompile.lock.txt
python3 .gitlab/check_dependency_coverage.py --input-only
