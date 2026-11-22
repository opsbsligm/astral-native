# astral-native


> **版权与商标**：*Astral Chain* © Nintendo。本仓为个人源码工程（fan project），未与任天堂关联、获其认可或赞助；*Astral Chain* 为任天堂注册商标，仅用于描述兼容性对象。仓库内官方宣传图见 [NINTENDO-ART-NOTICE.md](docs/NINTENDO-ART-NOTICE.md)；游戏代码（ExeFS）与 `prod.keys` 由用户从自有卡带提取提供，本仓不含；`controller-ui/` 系统级手柄 UI 资源的来源与口径见 [NINTENDO-ART-NOTICE.md](docs/NINTENDO-ART-NOTICE.md)。

《异界锁链》（Astral Chain，Switch 1.0.0 + 1.0.1 更新）的独立 Linux / Steam Deck 原生源码工程。基于上游 [astral-chain-pc-recomp](https://github.com/captainj-sparrow/astral-chain-pc-recomp)（MIT，totk-pc-recomp 管线：LLVM AArch64→x86-64 静态重编译 + Vulkan）固定 **1.5.0**（commit `194e0669`，见 [UPSTREAM.json](UPSTREAM.json)）；源码、构建工具和版本检查均在本仓库，与《旷野之息》《王国之泪》两独立仓同构，不依赖旧 `nativedeck` 工作区。

## 与两塞尔达的差距

对照《旷野之息》《王国之泪》已落实标准的逐项差距（上游已具备项 / 需适配项 / 需新做项 / Deck 未验证项）见 [docs/gap-matrix.md](docs/gap-matrix.md)。上游能力面（静态核验）：60fps 默认（社区 patch）+ 30 切换 + realtime/cutscene fix；FSR1 + SSAA 3D 渲染缩放；自定义分辨率；Deck 设备档案自动识别（DMI 或 SteamDeck=1，自动套 1280x800/handheld/ASTC→BC1/512MiB 纹理缓存）；SDL3 传感器；纯软件虚拟 Amiibo（540B NTAG215 转储）；模拟器格式金手指；设置与菜单简体中文。本仓另加 Deck 原生只读 IMU 后端，实体报告探测通过，游戏内使用待验（见 [native-motion.md](docs/native-motion.md)）。上游明确：**Steam Deck 本身尚未验证、未针对 4GB VRAM 优化**；60fps 下突进攻击输入计时存在已知 bug（第 4 幕教程建议临时 30fps）。

## 构建与运行（Linux / Deck 免 Docker）

需要 x86_64 Linux、clang/lld、Ninja、SDL3、libopus、libvpx、zstd、Vulkan 1.3（RADV 或 NVIDIA，需 `VK_EXT_external_memory_host`）、Linux 6.7+（write-watch 用 userfaultfd PAGEMAP_SCAN）、约 60 GiB 工作空间。完整工具链与步骤见 [docs/building.md](docs/building.md)（上游文档，Linux 节适用）。

先准备自己 dump 的输入（不进版本库）：base.nsp（`01007300020FA000`）、update-1.0.1.nsp（`01007300020FA800`）、prod.keys，在仓库根目录的私有 `config.local.toml` 中配置路径（文件已被 .gitignore 忽略）。以下示例假定 `[work] dir` 指向 `/mnt/astral-build`，并已按 [docs/building.md](docs/building.md) 完成工具链、提取、字体、shader translator 与静态重编译；不是从原始输入开始的一键构建：

```sh
git clone https://gitlab.example.com:8445/codex/astral-native.git
cd astral-native
# Run on an approved Linux build node after completing the prerequisites above.
.venv/bin/python tools/build_game.py --version v101 --gen generated/v101 --out /mnt/astral-build/v101
.venv/bin/python tools/package_build.py --version v101 --build /mnt/astral-build/v101 --extracted /mnt/astral-build/extracted/v101 --out /mnt/astral-build/package --with-romfs
/mnt/astral-build/package/astralchain
```

打包工具的 Linux 可执行文件名是 `astralchain`，当前不会生成 `run.sh`；可把该程序添加为非 Steam 游戏。个人运行目录含游戏派生内容；当前 Linux 打包器也未收齐全部共享库，目标机器仍需满足依赖要求，完整 Deck 包尚未验收。控制器走 Steam Input 普通手柄布局，无需 Proton。Deck 上 `DEVICE_PROFILE` 自动识别并套用 deck 档（见 [gap-matrix.md](docs/gap-matrix.md) A4）。

## 验收口径

两塞尔达同款输入契约：**游戏玩法按键保持原规则；所有菜单物理 Deck A 确认、B 取消；Deck 图示随实际绑定与菜单上下文；控制栏 角标→快捷面板→完整设置，纯触屏不依赖热键**。本仓当前为 G0 固定基线 + 差距矩阵阶段，`hardware_validated=false`，Deck 实机切片（G2）优先跑通 1.5.0 60fps + DECK 档，再按矩阵 B3/B4/D1 移植 Deck 图示、三级触屏控制栏与统一金手指。

## 掌机库条目（Steam 游戏模式）

发行包装好后，掌机库里还需要一条指向启动器的非 Steam 快捷方式，以及封面、海报和图标。
`docs/deck-grid/` 带着图一起完成这件事，全新 Deck 上不需要任何仓外文件：

    scp -r docs/deck-grid deck@DECK:/tmp/deck-grid-astral
    ssh deck@DECK /tmp/deck-grid-astral/deploy-deck-launcher.sh
    ssh deck@DECK /tmp/deck-grid-astral/deploy-deck-art.sh

`deploy-deck-launcher.sh` 安装 `astral-steam.sh`；`deploy-deck-art.sh` 调用同目录的
`deck-shortcut.py`：解析二进制 `shortcuts.vdf`，沿用 Steam 已分配给该启动器的 appid，
就地更新这一条，其余快捷方式按原字节重新序列化。四件图（横卡 920x430、竖海报 600x900、
hero 1920x620、图标 1254x1254）由 `gen-deck-art.py` 从 `docs/deck-grid/src/` 里的任天堂
官方宣传图按绝对坐标裁切重生成，`src/SHA256SUMS` 钉住源图内容。已装过再跑一遍不改动任何
字节；加 `--check` 只报告差异。多账号 Deck 传 `STEAM_ID`。改完在 Steam 里重启一次生效。

## 分享与恢复

源码分享目前暂停：现行私有仓仍跟踪四个游戏派生 UI 归档，`tools/check_content.py` 对 `controller-ui/` 的既有豁免不能证明仓库或历史干净。归档与历史先保全，完成使用方核查、受控存放及出站历史审查后再开放交付；游戏内容、密钥和存档不进入可分享源码。个人 `package/` 与源码交付分开；完整输入到 Deck 的构建和加密恢复链尚未验收，不能保证“克隆后一条命令即可开玩”。自己提供的游戏转储、密钥与着色器录制可以封装成项目私有的加密恢复制品，重置 Deck 后按 [个人恢复](docs/private-recovery.md) 一条命令重建。

## 许可与归属

上游代码 MIT（[LICENSE](LICENSE)）；第三方代码见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；许可不含 Nintendo 游戏本身。本仓为独立非商业个人项目。依赖与版本归属见 [UPSTREAM.json](UPSTREAM.json)、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 `docs/building.md`。
