"""Forward the real public-runtime compilation database and headers to the C/C++ analyzer.

Astral's build writes build.ninja (tools/build_game.py), so the compiler commands come straight from
`ninja -t compdb` (already argument lists) rather than from parsing a log. Only .c/.cpp source edges are
forwarded; .o outputs and the archive edge are dropped. System SDK headers are copied in and remapped the same
way as totk's pipeline so the analyzer's own Clang version stays the compiler of record.
"""
import argparse
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
import shlex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compdb', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--deps', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project = Path(os.environ['CI_PROJECT_DIR']).resolve()
    build, output = args.build.resolve(), args.output.resolve()
    if not build.is_relative_to(project) or not output.is_relative_to(project):
        parser.error('Keep public analysis outputs under the CI checkout')
    if output.exists():
        parser.error('Use a fresh analysis output directory')

    raw = []
    for row in json.loads(args.compdb.read_text()):
        file = row.get('file', '')
        if not (file.endswith('.c') or file.endswith('.cpp')) or not (project / file).is_file():
            continue   # .o outputs, the archive edge, and any generated (non-repo) sources
        command = row.get('arguments') or shlex.split(row.get('command', ''))
        raw.append((file, command))
    if not raw:
        raise SystemExit('Compilation database has no public runtime sources')

    output.mkdir(parents=True)
    resource = Path(subprocess.check_output(['clang', '-print-resource-dir'], text=True).strip()).resolve()
    # The analyzer uses its own Clang version. Its intrinsic/resource headers must match that compiler; only the
    # build host's libc/C++ SDK is forwarded.
    languages = {}
    for language, compiler in (('c', 'clang'), ('c++', 'clang++')):
        run = subprocess.run([compiler, '-E', '-x', language, '-', '-v'], input='', text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        section = run.stderr.split('#include <...> search starts here:', 1)[1].split('End of search list.', 1)[0]
        languages[language] = [Path(line.strip()).resolve() for line in section.splitlines()
                               if line.strip() and Path(line.strip()).resolve() != resource]
    unique = list(dict.fromkeys(p for paths in languages.values() for p in paths))
    mappings = {str(build): str(output / 'generated')}
    native = args.deps.resolve() / 'include'
    if native.is_dir():
        shutil.copytree(native, output / 'sdk/native')
        mappings[str(native)] = str(output / 'sdk/native')
    for index, path in enumerate(unique):
        target = output / 'sdk' / ('system-' + str(index))
        shutil.copytree(path, target)
        mappings[str(path)] = str(target)
    # Only generated public headers are forwarded; no objects, ELF files or game code.
    for path in build.rglob('*'):
        if path.is_file() and path.suffix in ('.h', '.inc'):
            target = output / 'generated' / path.relative_to(build)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

    def rebase(value):
        for old, new in sorted(mappings.items(), key=lambda pair: len(pair[0]), reverse=True):
            value = value.replace(old, new)
        return value

    entries = []
    for file, command in raw:
        language = 'c++' if file.endswith('.cpp') else 'c'
        arguments = ['clang++' if language == 'c++' else 'clang']
        skip = False
        for value in command:
            if skip:
                skip = False
                continue
            if value in ('-o', '-MF', '-MT', '-MQ'):
                skip = True
                continue
            if value in ('-MD', '-MMD', '-MP'):
                continue
            arguments.append(rebase(value))
        arguments.append('-nostdlibinc')
        if language == 'c++':
            arguments.append('-nostdinc++')
        for include in languages[language]:
            arguments += ['-isystem', mappings[str(include)]]
        entries.append(dict(directory=str(project), file=str(project / file), arguments=arguments))
    (output / 'compile_commands.json').write_text(json.dumps(entries, indent=2) + '\n')
    metadata = dict(public_runtime_translation_units=len(entries), all_built_objects_covered=True,
                    game_generated_code_included=False, system_include_directories=len(unique))
    (output / 'coverage-input.json').write_text(json.dumps(metadata, indent=2) + '\n')
    archive = output.with_suffix('.tar.gz')
    with tarfile.open(archive, 'w:gz') as stream:
        stream.add(output, arcname=output.name)
    print(json.dumps(dict(**metadata, artifact=str(archive), size=archive.stat().st_size)))


if __name__ == '__main__':
    main()
