"""Fetch, authenticate and restore this game's private package on a Linux host.

Which path runs is decided by the restored tree, not by a flag: a sealed release
(the seal-time component label is ``runtime``, so ``run.sh`` is at the top of the
restored folder) is verified in place and needs no compiler; raw build inputs
(``base.nsp``, ``update.nsp``, ``prod.keys`` under ``dump/``) go through the same
sequence as docs/building.md.
"""
import argparse
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import shutil

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 23
# The sealed release is about 10 GiB, and a low-peak restore holds the ciphertext plus
# one staged plaintext copy, so 32 GiB is the honest floor for the fast path. Raw inputs
# additionally need extraction (~21 GiB merged RomFS), the lift, and the build tree.
MIN_FREE_RESTORE = 32 * 1024 ** 3
MIN_FREE_BUILD = 160 * 1024 ** 3


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', default='https://www.bsligm.com:8445')
    p.add_argument('--version', required=True)
    p.add_argument('--token-file', required=True, type=Path)
    p.add_argument('--identity', required=True, type=Path)
    p.add_argument('--work', required=True, type=Path)
    p.add_argument('--encrypted-work', type=Path,
                   help='New directory on a separate disk for ciphertext only; plaintext stays in --work')
    p.add_argument('--low-peak', action='store_true',
                   help='Authenticate twice and stream restore without a plaintext archive copy')
    p.add_argument('--jobs', type=int, choices=(1, 2, 3, 4), default=2)
    p.add_argument('--cpu', choices=('v2', 'v3'), default='v3',
                   help='Target CPU level for a rebuilt binary (v3 needs AVX2)')
    a = p.parse_args()
    if '..' in a.work.parts:
        p.error('Parent traversal in work output refused')
    work = a.work.absolute()
    if work.exists() or work.is_symlink():
        p.error('Choose a new external work directory; no existing state is overwritten')
    if ROOT == work or ROOT in work.parents or work in ROOT.parents:
        p.error('Work must be outside the checkout')
    if any(v.is_symlink() for v in work.parents):
        p.error('Symlink output parent refused')
    existing = next(parent for parent in work.parents if parent.exists())
    if shutil.disk_usage(existing).free < MIN_FREE_RESTORE:
        p.error('Restoring a private package needs at least %d GiB free on the work volume'
                % (MIN_FREE_RESTORE // 1024 ** 3))
    encrypted_work = a.encrypted_work.absolute() if a.encrypted_work is not None else work
    if a.encrypted_work is not None:
        if '..' in a.encrypted_work.parts:
            p.error('Parent traversal in encrypted output refused')
        if encrypted_work.exists() or encrypted_work.is_symlink():
            p.error('Choose a new encrypted work directory; no existing state is overwritten')
        if ROOT == encrypted_work or ROOT in encrypted_work.parents or encrypted_work in ROOT.parents:
            p.error('Encrypted work must be outside the checkout')
        if work == encrypted_work or work in encrypted_work.parents or encrypted_work in work.parents:
            p.error('Plaintext and encrypted work directories must not overlap')
        if any(v.is_symlink() for v in encrypted_work.parents):
            p.error('Symlink encrypted output parent refused')
        encrypted_parent = next(parent for parent in encrypted_work.parents if parent.exists())
        if not encrypted_parent.is_dir():
            p.error('Encrypted output parent is not a directory')
        if shutil.disk_usage(encrypted_parent).free < 1024 ** 3:
            p.error('Encrypted work volume needs at least 1 GiB free before fetching')
    os.umask(0o077)
    work.mkdir(mode=0o700)
    if encrypted_work != work:
        encrypted_work.mkdir(mode=0o700)

    def run(*args):
        subprocess.run([sys.executable, *map(str, args)], check=True)

    run(ROOT / 'tools/recovery_gitlab.py', 'fetch', '--url', a.url, '--project', PROJECT,
        '--version', a.version, '--token-file', a.token_file, '--bundle', encrypted_work / 'encrypted')
    index = json.loads((encrypted_work / 'encrypted/index.json').read_text())
    if index.get('schema') == 2:
        raise SystemExit('Recovery sets (schema 2) are the Zelda repos; this game seals one payload')
    restore_options = ['--low-peak'] if a.low_peak else []
    run(ROOT / 'tools/recovery.py', 'restore', '--bundle', encrypted_work / 'encrypted',
        '--identity', a.identity, '--destination', work / 'restored', *restore_options)
    receipt = json.loads((work / 'restored/recovery-receipt.json').read_text())
    if receipt['missing']:
        raise SystemExit('Recovery authenticated and restored; rebuild blocked by recorded missing inputs: '
                         + ', '.join(receipt['missing']))
    entries = [work / 'restored' / prefix / 'run.sh' for prefix in ('', 'dump', 'runtime')]
    entries = [entry for entry in entries if entry.exists() or entry.is_symlink()]
    if len(entries) > 1:
        raise SystemExit('Ambiguous portable runtime entries; select a bundle with one run.sh')
    if entries:
        entry = entries[0]
        if entry.is_symlink() or not entry.is_file() or not os.access(entry, os.X_OK):
            raise SystemExit('Portable runtime entry is not a regular executable; reseal with schema 3')
        # run.sh --verify checks the release members and runs the binary's own selftest.
        subprocess.run([str(entry), '--verify'], check=True)
        print(str(entry))
        return

    dump = work / 'restored/dump'
    if not (dump / 'base.nsp').is_file():
        raise SystemExit('Restored bundle has neither run.sh nor dump/base.nsp; reseal one of the two shapes')
    if shutil.disk_usage(work).free < MIN_FREE_BUILD:
        raise SystemExit('Rebuilding from raw inputs needs at least %d GiB free on the work volume'
                         % (MIN_FREE_BUILD // 1024 ** 3))
    config = work / 'config.local.toml'
    config.write_text('[input]\nbase = %r\nupdate = %r\nkeys = %r\n[work]\ndir = %r\n'
                      % (str(dump / 'base.nsp'), str(dump / 'update.nsp'), str(dump / 'prod.keys'),
                         str(work / 'build')))
    run(ROOT / 'tools/extract.py', '--config', config)
    run(ROOT / 'tools/build_xlate.py')
    subprocess.run([sys.executable, str(ROOT / 'recomp/gen.py'), '--exefs',
                    work / 'build/extracted/v101/exefs', '--out', work / 'generated/v101',
                    '--patches', ROOT / 'recomp/patches-v101.txt', '--version', 'v101'], check=True)
    run(ROOT / 'tools/build_game.py', '--version', 'v101', '--gen', work / 'generated/v101',
        '--out', work / 'build/v101', '--jobs', a.jobs, '--cpu', a.cpu)
    # prepare_shaders reads the recorded variants from data/ or generated/, and a fresh
    # clone ships neither: the answers are recorded in play, so a rebuild without them
    # seeds nothing and every shader compiles during play. Restored bundles carry the copy.
    answers = next((candidate for candidate in
                    (dump / 'shader-answers.bin', work / 'restored/answers/shader-answers.bin')
                    if candidate.is_file()), None)
    if answers is None:
        raise SystemExit('Rebuilt release would ship without recorded shader variants: add '
                         'shader-answers.bin to the bundle (seal --include answers=...) or pass '
                         'a recording through tools/prepare_shaders.py --recordings')
    (work / 'generated').mkdir(exist_ok=True)
    shutil.copyfile(answers, work / 'generated/shader-answers.bin')
    run(ROOT / 'tools/prepare_shaders.py', work / 'build/v101', '--version', 'v101',
        '--answers', work / 'generated/shader-answers.bin', '--no-run')
    run(ROOT / 'tools/package_build.py', '--version', 'v101', '--build', work / 'build/v101',
        '--extracted', work / 'build/extracted/v101', '--out', work / 'package', '--with-romfs')
    print(str(work / 'package'))
    print('Next: tools/seal_private_package.py --portable %s --out <release> --commit <sha> '
          '--image <toolchain image id>, then tools/deploy_package.py' % (work / 'package'))


if __name__ == '__main__':
    main()
