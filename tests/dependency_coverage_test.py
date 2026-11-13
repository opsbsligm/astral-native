"""Scan the actual manifests and reject incomplete dependency SBOMs."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'dependency_coverage', Path(__file__).resolve().parents[1] / '.gitlab/check_dependency_coverage.py')
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.gitlab'))
import generate_scan_lock as lock_generator


class DependencyCoverage(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.enterContext(patch.object(coverage, 'ROOT', self.root))
        self.put('tools/requirements.txt', 'Alpha==1\n')
        self.put('tools/requirements-installer.txt', 'beta==2\n')
        self.put('tools/requirements-py314.txt', 'alpha==1\n')
        self.lock('alpha==1', 'beta==2', 'transitive==3')

    def put(self, name, content):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def lock(self, *pins):
        self.put('.gitlab/pipcompile.lock.txt', lock_generator.LOCK_HEADER + ''.join(
            pin + ' \\\n    --hash=sha256:' + 'a' * 64 + '\n' for pin in pins))

    def test_three_manifests_and_transitive_inventory_are_covered(self):
        self.assertEqual(coverage.validate_input(), {'alpha': '1', 'beta': '2', 'transitive': '3'})
        self.put('tools/requirements-py314.txt', 'alpha==4\n')
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            coverage.validate_input()

    def test_new_root_or_changed_version_cannot_silently_escape_scan(self):
        self.put('tools/requirements-installer.txt', 'beta==2\nnew-package==4\n')
        with self.assertRaisesRegex(ValueError, 'new-package'):
            coverage.validate_input()
        self.put('tools/requirements-installer.txt', 'beta==5\n')
        with self.assertRaisesRegex(ValueError, 'beta'):
            coverage.validate_input()

    def test_unhashed_lock_and_unhandled_manifest_syntax_fail(self):
        self.put('.gitlab/pipcompile.lock.txt', lock_generator.LOCK_HEADER + 'alpha==1\nbeta==2\n')
        with self.assertRaisesRegex(ValueError, 'hashes'):
            coverage.validate_input()
        self.put('tools/requirements.txt', '-r hidden.txt\n')
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            coverage.declared_dependencies()

    def test_scanner_header_must_be_on_the_second_line(self):
        path = self.root / '.gitlab/pipcompile.lock.txt'
        body = path.read_text().removeprefix(lock_generator.LOCK_HEADER)
        for prefix in ('', lock_generator.LOCK_HEADER.splitlines()[1] + '\n#\n'):
            self.put('.gitlab/pipcompile.lock.txt', prefix + body)
            with self.assertRaisesRegex(ValueError, 'header'):
                coverage.validate_input()

    def test_sbom_must_include_the_transitive_package_at_the_locked_version(self):
        source = 'sca-artifacts/gl-sbom-python.cdx.json'
        data = {'metadata': {'properties': [
            {'name': 'gitlab:dependency_scanning:input_file:path', 'value': 'tools/pipcompile.lock.txt'}]},
            'components': [{'name': 'alpha', 'version': '1'}, {'name': 'beta', 'version': '2'}]}
        self.put(source, json.dumps(data))
        args = ['coverage', '--sbom-dir', str(self.root / 'sca-artifacts')]
        with patch.object(sys, 'argv', args), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, 'omitted'):
                coverage.main()
            result = json.loads((self.root / 'out/dependency-coverage.json').read_text())
            self.assertEqual(result['missing']['tools/pipcompile.lock.txt'], {'transitive': '3'})
            data['components'].append({'name': 'transitive', 'version': '3'})
            self.put(source, json.dumps(data))
            coverage.main()
        self.assertTrue(json.loads((self.root / 'out/dependency-coverage.json').read_text())['complete'])

    def test_official_metadata_identity_and_artifact_hashes_are_required(self):
        data = {'info': {'name': 'Alpha', 'version': '1'},
                'urls': [{'digests': {'sha256': 'a' * 64}}, {'digests': {'sha256': 'b' * 64}}]}
        with patch.object(lock_generator, 'urlopen', return_value=io.BytesIO(json.dumps(data).encode())):
            self.assertEqual(lock_generator.artifact_hashes(('alpha', '1')),
                             ('alpha', '1', ['a' * 64, 'b' * 64]))
        data['info']['version'] = 'wrong'
        with patch.object(lock_generator, 'urlopen', return_value=io.BytesIO(json.dumps(data).encode())):
            with self.assertRaisesRegex(ValueError, 'identity'):
                lock_generator.artifact_hashes(('alpha', '1'))
        data['info']['version'] = '1'
        data['urls'][0]['digests']['sha256'] = 'bad'
        with patch.object(lock_generator, 'urlopen', return_value=io.BytesIO(json.dumps(data).encode())):
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                lock_generator.artifact_hashes(('alpha', '1'))

    def test_failed_metadata_fetch_preserves_existing_lock(self):
        resolved, output = self.root / 'resolved.txt', self.root / 'published.txt'
        resolved.write_text('alpha==1\n')
        output.write_text('previous')
        with patch.object(lock_generator, 'declared_dependencies', return_value={'alpha': '1'}), \
                patch.object(lock_generator, 'artifact_hashes', side_effect=OSError('offline')):
            with self.assertRaisesRegex(OSError, 'offline'):
                lock_generator.generate(resolved, output)
        self.assertEqual(output.read_text(), 'previous')
        self.assertEqual(list(self.root.glob('.pipcompile-*')), [])

    def test_generated_artifact_hash_lock_round_trips_through_scan_parser(self):
        resolved, output = self.root / 'resolved.txt', self.root / 'published.txt'
        resolved.write_text('alpha==1\ntransitive==3\n')
        records = lambda item: (item[0], item[1], ['a' * 64, 'b' * 64])
        with patch.object(lock_generator, 'declared_dependencies', return_value={'alpha': '1'}), \
                patch.object(lock_generator, 'artifact_hashes', side_effect=records), \
                contextlib.redirect_stdout(io.StringIO()):
            lock_generator.generate(resolved, output)
        packages = coverage.requirements(output)
        self.assertTrue(output.read_text().startswith(lock_generator.LOCK_HEADER))
        self.assertEqual(set(packages), {'alpha', 'transitive'})
        self.assertEqual(packages['alpha'], {'version': '1', 'hashes': {'a' * 64, 'b' * 64}})


if __name__ == '__main__':
    unittest.main()
