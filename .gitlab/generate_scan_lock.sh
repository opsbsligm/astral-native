#!/bin/sh
# Maintenance only: generate a real pip-compile input for the dependency scanner.
set -eu
cd "$(dirname "$0")/.."
export PIP_CONFIG_FILE=/dev/null PIP_INDEX_URL=https://pypi.org/simple PIP_EXTRA_INDEX_URL= PIP_NO_INDEX=0
python3 .gitlab/check_dependency_coverage.py --write-input out/dependency-lock/requirements.in
uv --no-config tool run --isolated --python 3.12 --with pip==26.3 --from pip-tools==7.6.2 \
  pip-compile --allow-unsafe --strip-extras --no-emit-index-url \
  --no-emit-trusted-host --no-header --no-annotate \
  --output-file out/dependency-lock/resolved.txt out/dependency-lock/requirements.in
python3 .gitlab/generate_scan_lock.py --resolved out/dependency-lock/resolved.txt \
  --output .gitlab/pipcompile.lock.txt
python3 .gitlab/check_dependency_coverage.py --input-only
