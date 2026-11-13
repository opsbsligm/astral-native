"""Exercise the real packager with original tiny files, including failed publication."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import package_build as package


class PackageBuild(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='astral-package-', dir=Path.cwd())
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.build = self.root / 'build/v101'
        self.output = self.root / 'build/v101-portable'
        self.inputs = {
            f'build/v101/astralchain{package.EXE}': b'original executable fixture',
            f'build/xlate/ac_xlate{package.EXE}': b'original translator fixture',
            'build/v101/romfs-index.bin': b'original index fixture',
            'build/v101/romfs-patches/patch.bin': b'original patch fixture',
            'build/extracted/v101/exefs/main': b'original module fixture',
            'build/extracted/firmware/shared-fonts/font.bin': b'original font fixture',
            **{f'build/v101/{name}': b'original library fixture' for name in package.DLLS},
        }
        for name, data in self.inputs.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        patch = mock.patch.object(package, 'ROOT', self.root)
        patch.start()
        self.addCleanup(patch.stop)

    def run_package(self, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            package.main(list(args))

    def test_default_build_and_published_program_belong_to_astral_chain(self):
        self.run_package('--no-shader-cache')
        self.assertEqual((self.output / f'astralchain{package.EXE}').read_bytes(),
                         self.inputs[f'build/v101/astralchain{package.EXE}'])
        self.assertFalse((self.output / f'totk{package.EXE}').exists())
        self.assertEqual((self.output / 'exefs/main').read_bytes(), b'original module fixture')
        self.assertEqual((self.output / 'shared-fonts/font.bin').read_bytes(), b'original font fixture')
        self.assertFalse(list(self.output.parent.glob('.v101-portable.staging-*')))

    def test_copy_failure_publishes_nothing_and_cleans_staging(self):
        real_copy = package.copy

        def fail_after_executable(source, destination):
            if Path(source).name.startswith('ac_xlate'):
                raise OSError('injected copy failure')
            real_copy(source, destination)

        with mock.patch.object(package, 'copy', fail_after_executable), self.assertRaises(OSError):
            self.run_package()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.output.parent.glob('.v101-portable.staging-*')))
        self.run_package()
        self.assertTrue((self.output / f'astralchain{package.EXE}').is_file())

    def test_existing_package_and_input_folders_are_preserved(self):
        self.output.mkdir()
        marker = self.output / 'keep.txt'
        marker.write_bytes(b'unique existing package')
        with self.assertRaises(SystemExit):
            self.run_package()
        self.assertEqual(marker.read_bytes(), b'unique existing package')
        for output in (self.build / 'nested', self.root / 'build/extracted/v101/exefs/nested'):
            with self.subTest(output=output), self.assertRaises(SystemExit):
                self.run_package('--out', str(output))
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
