"""Build the offscreen touch-chrome diagnostic on a Linux build node, without game inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new directory outside the source checkout')
    parser.add_argument('--deps', type=Path, required=True, help='approved SDK include/ and lib/ prefix')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('compile on a Linux build node')
    out = args.out.resolve()
    if out == ROOT or out.is_relative_to(ROOT) or out.exists() or args.out.is_symlink():
        parser.error('--out must be a new directory outside the source checkout')
    deps = args.deps.resolve()
    if not (deps/'include/vulkan/vulkan.h').is_file():
        parser.error('approved Vulkan development headers are missing')
    menu = (ROOT/'runtime/ui/menu.cpp').read_text()
    start = menu.index('static void style_init(')
    end = menu.index('static void make_context(', start)
    style = menu[start:end].strip()
    if not re.fullmatch(r'static void style_init\(ImGuiStyle &s\) \{[\s\S]*\}', style):
        parser.error('production style definition changed; inspect before rebuilding the probe')
    font = (ROOT/'runtime/ui/fonts/Roboto-Medium.ttf').read_bytes()
    out.mkdir(mode=0o700, parents=True)
    (out/'probe_style.inc.h').write_text(style+'\n')
    (out/'probe_font.inc.h').write_text('static const unsigned char probe_font[]={'+','.join(map(str,font))+'};\n')
    include = ['-I'+str(ROOT/'runtime'), '-I'+str(ROOT/'runtime/third_party/imgui'),
               '-I'+str(out), '-I'+str(deps/'include')]
    objects = []
    sources = [ROOT/'runtime/ui_text.c', ROOT/'tests/touch_vulkan_probe.cpp']
    sources += [ROOT/'runtime/third_party/imgui'/name for name in (
        'imgui.cpp','imgui_draw.cpp','imgui_widgets.cpp','imgui_tables.cpp','backends/imgui_impl_vulkan.cpp')]
    for i, source in enumerate(sources):
        obj = out/f'{i}.o'
        compiler, standard = ('clang','-std=gnu17') if source.suffix=='.c' else ('clang++','-std=c++17')
        subprocess.run([compiler,standard,'-O1','-g0',*include,'-c',str(source),'-o',str(obj)],check=True,timeout=90)
        objects.append(str(obj))
    exe = out/'touch_vulkan_probe'
    subprocess.run(['clang++',*objects,'-L'+str(deps/'lib'),'-lvulkan','-static-libstdc++','-static-libgcc',
                    '-pthread','-ldl','-o',str(exe)],check=True,timeout=45)
    metadata = {
        'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
        'executable_bytes':exe.stat().st_size,
        'sources':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        'production_style_sha256':hashlib.sha256(style.encode()).hexdigest(),
        'Roboto_sha256':hashlib.sha256(font).hexdigest(),
        'scope':'offscreen component; no full-game or real-touchscreen acceptance',
    }
    (out/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata))


if __name__ == '__main__':
    main()
