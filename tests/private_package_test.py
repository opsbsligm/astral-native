"""A sealed release must be byte-pinned, self-contained and swappable on a Deck.

Covers tools/seal_private_package.py (what goes into bundle.json, no symlinks, the
launcher's cache redirection) and the install/rollback path of
tools/deploy_package.py against that sealed tree.
"""
import importlib.util
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seal = load('seal_private_package', 'tools/seal_private_package.py')
deploy = load('deploy_package', 'tools/deploy_package.py')

LIBS = {'libSDL3.so.0.4.16': b'sdl bytes', 'libvpx.so.9.0.0': b'vpx bytes'}


class PrivatePackage(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='astral-seal-', dir=Path.cwd())
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.portable = self.base / 'portable'
        (self.portable / 'romfs').mkdir(parents=True)
        (self.portable / 'astralchain').write_bytes(b'\x7fELF game')
        (self.portable / 'romfs/romfs.bin').write_bytes(b'world data')
        self.libdir = self.base / 'libs'
        self.libdir.mkdir()
        for name, payload in LIBS.items():
            (self.libdir / name).write_bytes(payload)
        for link, target in (('libSDL3.so.0', 'libSDL3.so.0.4.16'), ('libvpx.so.9', 'libvpx.so.9.0.0')):
            (self.libdir / link).symlink_to(target)

    def seal(self, *extra):
        out = self.base / ('pkg%d' % len(list(self.base.glob('pkg*'))))
        command = [sys.executable, str(ROOT / 'tools/seal_private_package.py'),
                   '--portable', str(self.portable), '--out', str(out),
                   '--commit', 'a' * 40, '--image', 'sha256:abc'] + list(extra)
        result = subprocess.run(command, capture_output=True, text=True)
        return out, result

    def test_seal_pins_every_file_and_dereferences_library_links(self):
        out, result = self.seal('--lib-dir', str(self.libdir))
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((out / 'bundle.json').read_text())
        self.assertEqual(manifest['schema'], 1)
        self.assertEqual(manifest['source_commit'], 'a' * 40)
        self.assertEqual(set(manifest['files']),
                         {'astralchain', 'romfs/romfs.bin', 'run.sh', 'provenance.json',
                          'lib/libSDL3.so.0.4.16', 'lib/libSDL3.so.0',
                          'lib/libvpx.so.9.0.0', 'lib/libvpx.so.9'})
        for path in out.rglob('*'):
            self.assertFalse(path.is_symlink(), 'a release symlink would escape on swap: ' + str(path))
        self.assertEqual(manifest['files']['lib/libSDL3.so.0']['sha256'],
                         manifest['files']['lib/libSDL3.so.0.4.16']['sha256'])

    def test_launcher_moves_every_runtime_cache_out_of_the_release(self):
        out, result = self.seal('--lib-dir', str(self.libdir))
        self.assertEqual(result.returncode, 0, result.stderr)
        launcher = (out / 'run.sh').read_text()
        self.assertTrue((out / 'run.sh').stat().st_mode & 0o111, 'run.sh must stay executable')
        for variable in ('AC_PROFILE_DIR', 'AC_SHADER_CACHE', 'MESA_SHADER_CACHE_DIR', 'AC_PIPELINE_CACHE'):
            self.assertIn(variable, launcher)
        self.assertIn('--verify', launcher, 'the package must self-test before Steam launches it')
        self.assertIn('ASTRAL_VERIFY_OK', launcher)

    def test_seal_refuses_a_portable_folder_without_runtime_libraries(self):
        out, result = self.seal()   # no --lib-dir: nothing can stage libvpx
        self.assertEqual(result.returncode, 1)
        self.assertIn('libvpx.so.9', result.stderr)
        self.assertFalse((out / 'bundle.json').exists(), 'a partial package must not be published')


class DeploySealedRelease(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='astral-deploy-', dir=Path.cwd())
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'deck'
        (self.root / 'releases').mkdir(parents=True)
        self.package = self.base / 'package-origin'
        self.package.mkdir()
        (self.package / 'romfs').mkdir()
        (self.package / 'astralchain').write_bytes(b'\x7fELF game')
        (self.package / 'romfs/romfs.bin').write_bytes(b'world data')
        files = {path.relative_to(self.package).as_posix():
                 {'size': path.stat().st_size, 'sha256': deploy.digest(path)}
                 for path in sorted(self.package.rglob('*')) if path.is_file()}
        (self.package / 'bundle.json').write_text(json.dumps(
            {'schema': 1, 'source_commit': 'a' * 40, 'files': files}))

    def current(self):
        import os
        return os.readlink(self.root / 'current')

    def test_install_then_rollback_keeps_one_release_per_build(self):
        twin = self.base / 'package2'
        shutil.copytree(self.package, twin)   # install consumes the package tree

        target, previous, counts = deploy.install(self.package, self.root, 'r1')
        self.assertEqual(self.current(), 'releases/r1')
        self.assertIsNone(previous)
        self.assertEqual(counts['moved'], 3)
        self.assertFalse(self.package.exists(), 'the staging tree must not survive')
        self.assertEqual(len(list((self.root / 'releases').iterdir())), 1)

        _, _, counts = deploy.install(twin, self.root, 'r1')   # idempotent re-install
        self.assertEqual(counts.get('identical'), 1)
        self.assertEqual(self.current(), 'releases/r1')
        self.assertEqual(target.name, 'r1')
        self.assertEqual(len(list((self.root / 'releases').iterdir())), 1)

        (self.root / 'to-delete').mkdir()
        (self.root / 'to-delete/a').write_bytes(b'x')
        (self.root / 'to-delete/bundle.json').write_text('{"schema":1,"source_commit":"'
                                                         + 'b' * 40 + '","files":{}}')
        restored, left = deploy.rollback(self.root)
        self.assertEqual(self.current(), 'releases/r1')
        self.assertEqual(restored.name, 'r1')
        self.assertEqual(left, 'releases/r1')

    def test_a_package_file_that_changed_after_sealing_is_refused(self):
        (self.package / 'romfs/romfs.bin').write_bytes(b'swapped while copying')
        with self.assertRaisesRegex(ValueError, 'changed since packaging'):
            deploy.install(self.package, self.root, 'r1')
        self.assertFalse((self.root / 'releases/r1').exists())


if __name__ == '__main__':
    unittest.main()
