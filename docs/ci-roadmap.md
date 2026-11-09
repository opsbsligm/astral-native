# CI 路线图

首版（本仓已启用）：
- `content-check`：上游 `tools/check_content.py` 全量校验，游戏派生内容/密钥/生成代码不得入公仓。
- `native-unit`：不依赖游戏文件的纯 Python 单元（spin_waits 8、pack_shader_cache 5、installer 36）。
- `secret_detection`：GitLab Secret Detection（与 totk/botw 同镜像）。

下一 MR（对齐 totk/botw 完整门禁）：
1. `native-build`：Linux clang 构建 runtime（`tools/build_game.py` 自测 `--selftest`，需 clang/lld/sdl3/vulkan 工具链镜像 `native-games/toolchain:*`），产物含链接审计。
2. `gitlab-advanced-sast` + `gitlab-advanced-sast-cpp`（compile_commands）+ `semgrep-sast`：复用 totk `.gitlab/prepare_cpp_scan.py` 资产。
3. `container_scanning`（扫描工具链镜像）+ `dependency-scanning`/`dependency-coverage`（pip 依赖锁，需先落 astral 的 pipcompile.lock.txt）。
4. 远端 Runner 仅调度 Mac mini（Apple Silicon）/2018 MacBook Pro（Intel），禁用日用 Mac。

工具链说明：上游 Linux 构建需 clang+lld+ninja+sdl3+opus+libvpx+zstd+vulkan-headers+shaderc+spirv-tools（docs/building.md "Linux" 节）；shader 翻译器（.NET）在 Deck 侧构建时用 `prepare_shaders.py` 读预录制答案。
