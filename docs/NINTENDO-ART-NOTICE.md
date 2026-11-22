# 任天堂官方素材声明

本仓库 `docs/deck-grid/src/` 下存放了以下任天堂官方宣传素材的副本：

| 文件 | 内容 | 来源 |
|------|------|------|
| `astral-keyart.jpg` | 异界锁链官方横版宣传图 | © 2022 Nintendo. All rights reserved. |

仅用于 `gen-deck-art.py` 生成 Steam Deck 库封面，不随运行时分发。SHA-256 见同目录 `SHA256SUMS`。

**版权归属**：图片及其中角色、场景、字标版权归任天堂株式会社所有。本仓以个人 Steam 库封面用途使用，非商业、不重新分发、不修改像素。

**商标**：*Astral Chain* 是任天堂的注册商标，本仓仅用于描述兼容性对象。

**用户自带**：运行需要用户自行提取 ExeFS 与 `prod.keys`；本仓不含游戏代码（ExeFS）与密钥。

## `controller-ui/` 目录说明

`controller-ui/` 下 4 个 `ui_core.dat`（PlayStation/Xbox 各一份、含 `_us` 变体）为 Switch 系统级手柄 UI 资源，随上游项目公开分发。本仓未修改其中任何一个：四个文件的 Git blob 与上游公开仓 [captainj-sparrow/astral-chain-pc-recomp](https://github.com/captainj-sparrow/astral-chain-pc-recomp)（MIT，2026-11-22 核验）逐字节一致：

```
1808541ba305cec12c9c8a4da05aaa3eca82761f  controller-ui/{playstation/RomFS,xbox/romfs}/ui/ui_core.dat
521e6b34a9b67e74128217e30f078bfecb77b822  controller-ui/{playstation/RomFS,xbox/romfs}/ui/ui_core_us.dat
```

上游未对其附独立版权声明，本仓沿用上游 MIT 授权与"公开项目自带素材"的既有口径；如需追溯，见上游仓 `controller-ui/` 同名文件。其余 18 个 `.dtt` 字体文件未随本仓公开（私有构建仍从上游提取）。

**生成物**：`docs/deck-grid/*.png` 为 `docs/deck-grid/src/` 源图的派生生成物，随源图许可。

*This project is not affiliated with, endorsed by, or sponsored by Nintendo.*
