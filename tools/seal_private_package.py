"""Seal a package_build.py output into a deploy_package-compatible private package."""
import argparse, hashlib, json, os, shutil
from pathlib import Path

MANIFEST = 'bundle.json'
# Runtime caches (Mesa's driver cache, our translated-shader cache, the Vulkan pipeline
# cache and the save profile) live beside the exe unless told otherwise, so a release
# folder would grow while it runs and a rebuild could not hardlink it cleanly. Point them
# at <root>/data, one level up: the release itself stays a read-only, byte-pinned tree.
RUN_SH = '''#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
# $here is <root>/releases/<id> once the release symlink is resolved, so the shared data
# folder sits two levels up: every release of this game reads one profile and one cache.
data=$(CDPATH= cd -- "$here/../.." && pwd -P)/data
mkdir -p "$data/profile" "$data/shader-cache" "$data/mesa-cache"
export AC_PROFILE_DIR="$data/profile"
export AC_SHADER_CACHE="$data/shader-cache"
export MESA_SHADER_CACHE_DIR="$data/mesa-cache"
export AC_PIPELINE_CACHE="$data/pipeline-cache.bin"
if [ "${1:-}" = "--verify" ]; then
  test -x "$here/astralchain"
  test -f "$here/romfs/romfs.bin"
  test -f "$here/romfs-index.bin"
  test -f "$here/seed-programs.bin"
  test -f "$here/lib/libSDL3.so.0.4.16"
  test -f "$here/lib/libvpx.so.9.0.0"
  export LD_LIBRARY_PATH="$here/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  "$here/astralchain" --selftest
  echo "ASTRAL_VERIFY_OK"
  exit 0
fi
export SteamDeck=1
export LD_LIBRARY_PATH="$here/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$here/astralchain" "$@"
'''
# Cache that must never ship inside a release: it is written at run time next to the
# exe, so a sealed release keeps it in the profile directory instead (see launcher).
EXCLUDE = {'run.sh'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def place_regular(source, destination):
    """Hardlink a package file, dereferencing symlinks so the tree holds real bytes.

    deploy_package.py refuses a package with symlinks (a symlink inside a release would
    escape the release directory when releases are swapped), so the versioned library and
    its SONAME link both ship as plain files.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        shutil.copyfile(source, destination)
        os.chmod(destination, 0o644)
    else:
        os.link(source, destination)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--portable', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--image', required=True, help='docker image id of the toolchain that built the exe')
    a = ap.parse_args()
    src, out = a.portable.resolve(), a.out.resolve()
    assert src.is_dir() and not out.exists(), (src, out)
    files, extras = {}, []
    out.mkdir(parents=True)
    for path in sorted(p for p in src.rglob('*') if p.is_file()):
        rel = path.relative_to(src).as_posix()
        if rel in EXCLUDE:
            continue
        placed = out / rel
        place_regular(path, placed)
        files[rel] = {'size': placed.stat().st_size, 'sha256': digest(placed)}
    # The launcher is generated here, so the sealed tree is self-contained and byte-pinned.
    (out / 'run.sh').write_text(RUN_SH)
    os.chmod(out / 'run.sh', 0o755)
    files['run.sh'] = {'size': (out / 'run.sh').stat().st_size, 'sha256': digest(out / 'run.sh')}
    provenance = {
        'source_commit': a.commit,
        'image_id': a.image,
        'package_source': str(src),
        'scope': 'private Deck release rebuilt from main HEAD; shader seeds and translator reused only when byte-identical',
        'hardware_validated': False,
    }
    (out / 'provenance.json').write_text(json.dumps(provenance, indent=2, sort_keys=True) + '\n')
    files['provenance.json'] = {'size': (out / 'provenance.json').stat().st_size,
                                'sha256': digest(out / 'provenance.json')}
    manifest = {'schema': 1, 'source_commit': a.commit, 'files': files, 'provenance': provenance}
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print('SEALED', out, 'files', len(files))
    for extras_name in extras:
        print('extra', extras_name)


if __name__ == '__main__':
    main()
