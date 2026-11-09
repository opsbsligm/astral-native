# Astral Chain → Steam Deck 原生：对标 BOTW/TOTK 标准的差距矩阵

上游基线：captainj-sparrow/astral-chain-pc-recomp **1.5.0**（commit `194e0669`，MIT，2026-11-09 固定）。
管线：totk-pc-recomp（LLVM AArch64→x86-64 静态重编译 + Vulkan），与 TOTK 同管线，复用度高。
验收标准：沿用两塞尔达的 97 项矩阵（18 基线 + 63 计划 + 16 盲区）与输入契约（世界玩法原语义 / 菜单 A确认 B取消 / Deck 图示随绑定 / 三级触屏 chrome）。

状态标记：`有`=上游已具备且静态核验；`部分`=存在但需适配/实机确认；`缺`=需移植或新做；`Deck未验`=存在但上游明确未在 Deck 验证。

## A. 执行路径与平台
| # | 能力 | 上游状态 | 证据 | 对齐两塞尔达标准的差距 |
|---|------|---------|------|----------------------|
| A1 | 原生 x86-64（AOT，非模拟） | 有 | AGENTS.md、docs/architecture.md | 达标，需在 Deck 实机确认进程/热点 |
| A2 | Vulkan 渲染（NVN→Vulkan） | 有 | runtime/vk_*.c | 达标；Deck 用 RADV（Van Gogh）需实机 |
| A3 | Linux/SDL3 运行（非仅 Windows） | 部分 | docs/building.md:148 "Linux (in progress)"；1.4.3 在 RADV RX6600/VEGA7 可玩 | 上游明确"Steam Deck 本身未验证"→ 需 Deck 实测 |
| A4 | Steam Deck 设备档案自动识别 | 有 | cfg.c:293 on_steam_deck()（DMI Valve/Jupiter/Galileo 或 SteamDeck=1） | 达标；DECK[] 档自动套 handheld/1280x800/30fps/ASTC→BC1/512MiB |
| A5 | 4GB VRAM 优化 | 缺 | README "Planned: Optimizations for 4gb VRAM GPU and Steam Deck" | DECK 档已压（ASTC→BC1、tex 512MiB、shadow 512），但未实测→需压测确认 |

## B. 输入 / 图示 / 菜单
| # | 能力 | 上游状态 | 证据 | 差距 |
|---|------|---------|------|------|
| B1 | 游戏内玩法按键保持原规则 | 有 | input.c 合并 SDL 手柄+键盘+鼠标；AC_BIND_* 可重绑 | 达标 |
| B2 | 菜单 A确认/B取消 | 部分 | 上游设置菜单为 ImGui（F1），键位默认；未见"A确认B取消"明确策略 | 需移植 menu_confirm 策略（两塞尔达已有 menu_confirm.c） |
| B3 | Deck/Valve 手柄图示 | 缺 | cfg.c:142 PROMPTS auto/nintendo/xbox/playstation；controller-ui/ 仅 xbox+playstation 两套 dtt | 上游无 Valve 家族图标→需做 Deck 图示（两塞尔达已有 draw_deck_art.py 体系） |
| B4 | 三级触屏控制栏（角标→快面板→全设置） | 缺 | 上游为 F1 ImGui 设置菜单 + F10 性能覆盖层，键盘热键触发 | 需移植我们的 control_bar（badge→quick→full、纯触屏、8向锚点） |
| B5 | 触屏/手柄 QTE 提示 | 部分 | 有按钮提示体系（make_prompts_folders） | 需 Deck 布局下核对 QTE（异界锁链多连招/QTE 密集） |

## C. 画面 / 性能
| # | 能力 | 上游状态 | 证据 | 差距 |
|---|------|---------|------|------|
| C1 | FSR（上采样） | 部分 | ini upscaler=fsr（AMD FSR 1）+ ssaa（3D render scale） | 有 FSR1；需确认 Deck 上 FSR1 生效+标注（两塞尔达：TOTK FSR1+诚实标注3/4不可用） |
| C2 | 抗锯齿 | 部分 | ssaa 3D render scale（1080 底渲染放大） | 需 Deck 实机核对 |
| C3 | 分辨率 | 有 | output_res/render_scale/window_size 可配；DECK 档 1280x800 | 达标 |
| C4 | 帧率（解 30 锁/60fps） | 有 | fps=60 默认（社区 60fps patch）+30 切换 + highfps_fix + realtime + cutscene fix | 达标；**但 60fps 下突进攻击输入计时 bug 已知**（README Status），第4幕教程需临时 30fps |
| C5 | ASTC 纹理（Deck 无原生 ASTC） | 有 | cfg.c:187 Deck 走 compute decoder（vk_astc.c）；DECK 档 ASTC→BC1/BC3 | 达标；性能代价需在 Deck 实测 |
| C6 | Deck 实测帧率/功耗 | 缺 | 上游未测 Deck | 需 NVN p50/present 中位实测（两塞尔达有 present/帧时间口径） |

## D. 扩展功能
| # | 能力 | 上游状态 | 证据 | 差距 |
|---|------|---------|------|------|
| D1 | 金手指 | 部分 | [cheats] per-mod 模拟器格式（mods/<mod>/cheats/<build>.txt），Cheats 标签写 ini | 格式与两塞尔达"版本绑定 Atmosphere 数据金手指"不同→需统一为可核实生效的预设体系 |
| D2 | Amiibo（虚拟可刷） | 有 | amiibo.c/h 纯软件 540B NTAG215 转储 + amiibo_set_device_present + load_file/scan_and_tap；ov_system.c nn::nfp IPC | 有虚拟注入能力（与 TOTK 同路）→需 Deck 实机确认奖励生效 |
| D3 | 原生陀螺仪 IMU | 有 | input.c "gyro are used when SDL exposes them"（SDL3 sensor 直读） | 与两塞尔达 SDL_SENSOR 直读同路→需 Deck 实机确认方向/瞄准 |
| D4 | 中文化 | 部分 | 设置与菜单支持简体中文（Setup + in-game menu）；controller-ui 有 cn.dtt | 游戏内文本语言可选；需确认中文覆盖完整度 |

## E. 恢复 / 构建 / 发布
| # | 能力 | 上游状态 | 证据 | 差距 |
|---|------|---------|------|------|
| E1 | 输入即构建（自己 dump 的游戏+key） | 有 | config.local.toml（base.nsp/update.nsp/prod.keys），build 在本机 | 达标；需 NAS 私有输入 + 加密恢复（两塞尔达已有私有恢复 schema） |
| E2 | 游戏内容不进公仓 | 有 | check_content.py GENERATED_MARKER 校验 + .gitignore 大文件规则 | 达标；CI 跑同一校验 |
| E3 | 可复现构建/CI | 部分 | 上游 CI 在 GitHub（.github/）；Linux 构建需 clang/lld/sdl3/vulkan | 需套我们的 GitLab CI（unit→build→SAST/Secret/Container/Dependency，远端 native-games tag） |
| E4 | Deck 运行包（无 Docker 依赖） | 缺 | 上游 Windows 是 AppImage/Setup.exe；Linux 链接系统库 $ORIGIN rpath | 需出 Deck 免 Docker 运行包（两塞尔达已有 run.sh --verify 体系） |
| E5 | 存档保护/原子快照 | 部分 | 有存档数据（README "its save data"）；未见原子快照 | 需移植两塞尔达的存档去重+原子快照+回滚 |

## 关键结论
1. **管线同源**：与 TOTK 同 totk-pc-recomp 管线，ASTC/compute-decode、write-watch shadow、input/amiibo/cheats 子系统可直接对照 TOTK 移植路径，复用度最高。
2. **最大缺口**：Deck 本身未验证（上游明说）、4GB VRAM 未优化、无 Valve 图示家族、无三级触屏控制栏、金手指格式与两塞尔达不统一、无 Deck 免 Docker 运行包。
3. **已知硬伤**：60fps 突进攻击输入计时 bug（第4幕需临时 30fps）——需列入 Deck 实测确认是否影响可玩性。
4. **优先切片**（对齐 G2 阶段）：先 Deck 实机跑通 1.5.0（60fps+DECK档）→确认帧率/ASTC decode 代价→再按 B3/B4/D1 移植图示/控制栏/金手指。

> 静态核验基于 1.5.0 源码；`Deck未验` 项一律 hardware_validated=false，待 Deck 实机补齐。
