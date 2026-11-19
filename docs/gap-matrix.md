# Astral Chain → Steam Deck 原生：对标 BOTW/TOTK 标准的差距矩阵

上游基线：captainj-sparrow/astral-chain-pc-recomp **1.5.0**（commit `194e0669`，MIT，2026-11-09 固定）。
管线：totk-pc-recomp（LLVM AArch64→x86-64 静态重编译 + Vulkan），与 TOTK 同管线，复用度高。
验收标准：沿用两塞尔达的 97 项矩阵（18 基线 + 63 计划 + 16 盲区）与输入契约（世界玩法原语义 / 菜单 A确认 B取消 / Deck 图示随绑定 / 三级触屏 chrome）。

原始标准的逐项定义与来源摘要已固化到 [standard-register.json](acceptance/standard-register.json)。
97 条中 84 条适用于异界锁链，13 条为战神/血源专属场景，作为参考保留原 ID；
这些参考项不计作异界锁链验收通过。适用项尚未挂接精确构建与实测证据，统一保持 `not_run`。
本表“上游有实现”也不等于标准已通过，当前 `hardware_validated=false`。

状态标记：`有`=上游已具备且静态核验；`部分`=存在但需适配/实机确认；`缺`=需移植或新做；`Deck未验`=存在但上游明确未在 Deck 验证。

## A. 执行路径与平台
| # | 能力 | 上游状态 | 证据 | 对齐两塞尔达标准的差距 |
|---|------|---------|------|----------------------|
| A1 | 原生 x86-64（AOT，非模拟） | 有 | AGENTS.md、docs/architecture.md | CPU 管线存在；Deck 进程、依赖与热点仍需实证 |
| A2 | Vulkan 渲染（NVN→Vulkan） | 有 | runtime/vk_*.c | 后端存在；Deck/RADV 画面与同步仍需实测 |
| A3 | Linux/SDL3 运行（非仅 Windows） | 部分 | runtime/platform/linux.c；公开 CI 构建 runtime 静态库 | 旧文档的 TOTK 1.2.1/1.4.3 帧率不能作本作证据；完整 Astral Chain 1.0.1/Deck 待验 |
| A4 | Steam Deck 设备档案自动识别 | 有 | cfg.c:293 on_steam_deck()（DMI Valve/Jupiter/Galileo 或 SteamDeck=1） | 档案存在；需读回 handheld/1280x800/30fps/ASTC→BC1/512MiB 等实际默认值及优先级 |
| A5 | 4GB VRAM 优化 | 缺 | README "Planned: Optimizations for 4gb VRAM GPU and Steam Deck" | DECK 档已压（ASTC→BC1、tex 512MiB、shadow 512），但未实测→需压测确认 |

## B. 输入 / 图示 / 菜单
| # | 能力 | 上游状态 | 证据 | 差距 |
|---|------|---------|------|------|
| B1 | 游戏内玩法按键保持原规则 | 有 | input.c 合并 SDL 手柄+键盘+鼠标；AC_BIND_* 可重绑 | 达标 |
| B2 | 菜单 A确认/B取消 | 部分 | input_pad_read 的 Deck 应用菜单采样独立使用物理 south/east，不受玩法绑定影响 | 已补应用层菜单；原作游戏菜单、图示和 QTE 的上下文规则仍待适配及实机核对 |
| B3 | Deck/Valve 手柄图示 | 缺 | cfg.c:142 PROMPTS auto/nintendo/xbox/playstation；controller-ui/ 仅 xbox+playstation 两套 dtt | 上游无 Valve 家族图标→需做 Deck 图示（两塞尔达已有 draw_deck_art.py 体系） |
| B4 | 三级触屏控制栏（角标→快面板→全设置） | 部分 | ui/touch_chrome.h + menu_sdl.cpp；docs/touch-menu.md | 三级入口、8向停靠与持久化已接；Deck RADV 1280×800 离屏角标/快捷面板及中文输出通过。实际游戏合成、完整设置画面和实体触屏仍待验，不提高 97 项登记状态 |
| B5 | 触屏/手柄 QTE 提示 | 部分 | 有按钮提示体系（make_prompts_folders） | 需 Deck 布局下核对 QTE（异界锁链多连招/QTE 密集） |

## C. 画面 / 性能
| # | 能力 | 上游状态 | 证据 | 差距 |
|---|------|---------|------|------|
| C1 | FSR（上采样） | 部分 | ini upscaler=fsr（AMD FSR 1）+ ssaa（3D render scale） | 有 FSR1；需确认 Deck 上 FSR1 生效+标注（两塞尔达：TOTK FSR1+诚实标注3/4不可用） |
| C2 | 抗锯齿 | 部分 | ssaa 3D render scale（1080 底渲染放大） | 需 Deck 实机核对 |
| C3 | 分辨率 | 有 | output_res/render_scale/window_size 可配；DECK 档 1280x800 | 需分别核对内部尺寸、窗口输出与真正 16:10 布局 |
| C4 | 帧率（解 30 锁/60fps） | 有 | fps=60 通用默认与 30 切换；highfps_fix/realtime/cutscene fix | 固定上游快照声明 60fps 突进输入计时问题、第4幕暂用30fps；本机尚未复现，需核对 Deck 档默认及完整时间语义 |
| C5 | ASTC 解码与转码 | 有 | cfg.c:187 Deck 走 compute decoder（vk_astc.c）；DECK 档 ASTC→BC1/BC3 | 实现存在；sRGB/透明/法线、3D ASTC 和实际性能仍待验 |
| C6 | Deck 实测帧率/功耗 | 缺 | 上游未测 Deck | 需 NVN p50/present 中位实测（两塞尔达有 present/帧时间口径） |

## D. 扩展功能
| # | 能力 | 上游状态 | 证据 | 差距 |
|---|------|---------|------|------|
| D1 | 金手指 | 部分 | [cheats] per-mod 布局（mods/<mod>/cheats/<build>.txt），Cheats 标签写 ini | 需核对实际操作码、精确版本绑定和写回校验；不能仅凭格式名判断与两作兼容性 |
| D2 | Amiibo（虚拟服务） | 部分 | 继承的 amiibo.c/h 540B 转储读取与 ov_system.c nn::nfp IPC | 服务代码存在不等于本作会调用或有奖励玩法；须先确认原作适用性，再验证实际行为，不能计作已支持刷奖励 |
| D3 | 原生陀螺仪 IMU | 部分 | input.c 现有运动线程 + deck_motion_linux.c 只读原生后端；docs/native-motion.md | 组件回归通过；2026-11-15 Deck 只读探测 5 秒收到 1,222 个新样本，描述符恢复原数。仅证明该会话的实体报告可用性；Steam 档案变化、方向/瞄准及游戏内生效未验，不改变 97 项登记状态 |
| D4 | 中文化 | 部分 | 设置与菜单支持简体中文（Setup + in-game menu）；controller-ui 有 cn.dtt | 游戏内文本语言可选；需确认中文覆盖完整度 |

## E. 恢复 / 构建 / 发布
| # | 能力 | 上游状态 | 证据 | 差距 |
|---|------|---------|------|------|
| E1 | 输入即构建（自己 dump 的游戏+key） | 有 | config.local.toml 指向 base/update 与密钥；代码、输入、生成物分离 | 需在获准私有构建节点验证完整流程及加密恢复，不在日用 Mac 或 Deck 构建 |
| E2 | 游戏内容不进公仓 | 部分 | check_content.py 对 controller-ui/ 有既有豁免；四个游戏派生 UI 归档仍被跟踪 | 仓库当前为私有，未建立公开传播证据；整体内容边界不达标，保持发布关闭，先核使用方与受控保全，再处理现行树及历史；不以暂存区检查通过代替全历史审查 |
| E3 | 可复现构建/CI | 部分 | 本仓已配置 unit/runtime-build、SAST/Secret/Container/Dependency 与 SBOM 覆盖门禁 | 需精确 HEAD、实际远端 Runner 与合并后 main 全部终态通过；配置存在不是验收通过 |
| E4 | Deck 运行包（无 Docker 依赖） | 缺 | Windows 为 .exe/Setup；Linux 构建链接系统库并使用 $ORIGIN rpath | 便携打包已修复 v101/astralchain 与原子发布；本项目完整自包含 Deck 包仍未验 |
| E5 | 存档保护/原子快照 | 部分 | 有存档数据（README "its save data"）；未见原子快照 | 需移植两塞尔达的存档去重+原子快照+回滚 |

## 关键结论
1. **管线同源**：与 TOTK 同 totk-pc-recomp 管线，ASTC/compute-decode、write-watch shadow、input/amiibo/cheats 子系统可直接对照 TOTK 移植路径，复用度最高。
2. **最大缺口**：Deck 本身未验证（上游明说）、4GB VRAM 未优化、无 Valve 图示家族、无三级触屏控制栏、金手指格式与两塞尔达不统一、无 Deck 免 Docker 运行包。
3. **已知硬伤**：60fps 突进攻击输入计时 bug（第4幕需临时 30fps）——需列入 Deck 实测确认是否影响可玩性。
4. **优先切片**（对齐 G2 阶段）：先 Deck 实机跑通 1.5.0（60fps+DECK档）→确认帧率/ASTC decode 代价→再按 B3/B4/D1 移植图示/控制栏/金手指。

> 静态核验基于 1.5.0 源码；`Deck未验` 项一律 hardware_validated=false，待 Deck 实机补齐。

## F. 竞品吸收（与两塞尔达子矩阵同步，2026-11-10）

竞品调研（Savage Wind / sigma·totk-recomp / valentderah totk-pc-recomp / MacNativeGames）筛出 5 项可吸收能力，两塞尔达已各建独立子矩阵（botw-native/docs/competitor-adoption.md、totk-native/docs/competitor-adoption.md，5 项 hardware_validated=false）。本仓作为第三作，同样列为对标缺口，验收口径一致（Deck 实跑截图+配置读回）：

| # | 能力 | 上游状态 | 差距 |
|---|------|---------|------|
| F1 | shader 后台预热（不阻塞首入场景） | 部分 | 上游 shader 在 install 期预编译（"Shaders prepared at install"），无"游戏中首入场景后台继续"运行时预热；需对照两塞尔达 CA1 补后台不阻塞路径 |
| F2 | >30fps 衍生界面 bug（快速菜单/游戏结束） | 部分 | 上游 60fps 默认+cutscene speed fix，但已知 60fps 突进攻击输入计时 bug（第4幕需临时 30fps）；快速菜单/游戏结束在 60 帧未逐项核对，需对照 CA2 用 romfs overlay 同法修 |
| F3 | 画面页 FOV/阴影分辨率/各向异性16x | 部分 | 上游 FSR1+ssaa+16x 各向异性已声明（README "Anisotropic texture filtering up to 16x"），FOV 滑块/阴影分辨率档位未见；需对照 CA3 暴露/补齐 |
| F4 | mods 系统（RomFS+ExeFS 代码补丁+HD 贴图包） | 部分 | 上游有 per-mod 模拟器格式 mods（`mods/<mod>/`），但 ExeFS `.ips`/`.pchtxt` 自动重编译、HD 贴图堆自动扩容未见；需对照 CA4 统一 |
| F5 | 144fps 实验档 + F10 性能浮层 | 部分 | 上游有 F10 性能覆盖层（README "performance overlay (F10)"）+60/30 切换，144 实验档未见；需对照 CA5 对齐 |

DLSS 需匹配 NVIDIA 硬件与后端，不能把开关存在当作 Deck 上已生效。
HDR 按内置 LCD/OLED、外接显示、Vulkan 交换链与 Gamescope 色彩链分别验收；
[OLED 官方规格明确列出 HDR 显示](https://www.steamdeck.com/en/tech/oled)，不能笼统写成“Deck 不支持”。
本作 HDR 路径未验，通过前保留正确 SDR 回退。
