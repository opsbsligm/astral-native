#!/usr/bin/env python3
"""从 docs/deck-grid/src 里的任天堂官方宣传图重生成 Steam 库四件套。

源图随仓库走：任天堂 eu 站这张 2000x1000 分享图是唯一还在线的官方横版主视觉，
两塞尔达用过的媒体站 CDN 早已 403，只记 URL 的话换机器取不回同一批像素。
源图 SHA-256 见 src/SHA256SUMS。

  astral-keyart.jpg  2000x1000 官方主视觉：左男警、中 Chimera 面具、右女警，
                     ASTRAL CHAIN 字标压在画面下半中央

四件都从这张主视觉取，画面里必有角色或字标。裁切框按目标尺寸的宽高比反推，
所以缩放是等比 Lanczos，不会拉伸变形；每个框生成前先核比例（见 _check）。

    python3 docs/deck-grid/gen-deck-art.py [输出目录，默认本目录]

四件尺寸是 Steam Deck 库规格：横卡 920x430、竖海报 600x900、
详情页 hero 1920x620、快捷方式图标 1254x1254。装到掌机用同目录的
deploy-deck-art.sh。
"""
import hashlib
import pathlib
import sys
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE
KEYART = HERE / "src" / "astral-keyart.jpg"

PLAN = {
    # out 文件名: (裁切框, 目标尺寸)。源图 2000x1000。
    # 横卡取全幅去掉顶部 65px 天空，正好 2000x935 与 920x430 同比例，
    # 三人同框且字标完整。
    # hero 只取上半 2000x646（1920:620），左侧留给 Steam 详情页自己的标题，
    # 下沿停在字标上方，避免与 Steam 覆盖的按钮区打架。
    # 竖海报取正中 667x1000（2:3）：Chimera 面具与字标同框，两侧角色各留半个身位。
    # 图标取正中 1000x1000 方形：面具在上、字标在下，库缩略图尺寸下认得出是哪部游戏。
    "astral-grid.png": ((0, 65, 2000, 1000), (920, 430)),
    "astral-hero.png": ((0, 0, 2000, 646), (1920, 620)),
    "astral-grid-p.png": ((667, 0, 1334, 1000), (600, 900)),
    "astral-shortcut-icon.png": ((700, 0, 1700, 1000), (1254, 1254)),
}


def _check(box, size, name):
    w, h = box[2] - box[0], box[3] - box[1]
    want, got = size[0] / size[1], w / h
    if abs(want - got) / want > 0.005:
        raise SystemExit("%s: 裁切框 %dx%d 与目标 %dx%d 宽高比不符（%.2f%% 偏差）"
                         % (name, w, h, size[0], size[1], abs(want - got) / want * 100))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (box, size) in PLAN.items():
        im = Image.open(KEYART).convert("RGB")
        l, t, r, b = box
        assert 0 <= l < r <= im.width and 0 <= t < b <= im.height, "%s box %s 越界" % (name, box)
        _check(box, size, name)
        im.crop(box).resize(size, Image.LANCZOS).save(OUT / name, "PNG")
        print("%-27s %sx%s  %s" % (name, size[0], size[1],
                                   hashlib.sha256((OUT / name).read_bytes()).hexdigest()[:16]))


if __name__ == "__main__":
    main()
