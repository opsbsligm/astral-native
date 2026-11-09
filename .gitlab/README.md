# CI 资产（对齐 totk/botw 门禁）

本目录与 `totk-native`、`botw-native` 的同名资产同源，按游戏构建方式做了最小适配。

## 当前由 `.gitlab-ci.yml` 使用

- `prepare_cpp_scan.py` — astral 构建用 `tools/build_game.py` + `ninja -t compdb`（无 runtime.log），
  直接从 compile_commands.json 取参数；过滤 `.o` 与 archive 边，仅转发 `.c/.cpp` 运行时源。
  系统 SDK 头与 `$NATIVE_DEPS/include` 拷贝到 `out/cppscan/sdk/` 并重映射，
  分析器自带 clang 保持为记录编译器（与 totk 同策略）。
- `unpack_cpp_scan.py` / `run_cpp_scan.py` / `sast-ruleset.toml` / `clangsa-resources.yml` — 与 totk 一致。

## 下一 MR 启用（见 docs/ci-roadmap.md）

- `fetch_toolchain.rb` / `prepare_scanner_cache.rb` / `run_container_scan.rb` / `toolchain.env`
  — container_scanning 扫描 CI 工具链镜像。启用前需在本项目登记 `native-toolchain` 通用包
  （`toolchain.env` 的 version/sha256 届时指向 p23 自己的包）。
- `check_dependency_coverage.py` / `generate_scan_lock.sh`
  — dependency-scanning 需要 `requirements-build.lock` 与 `.gitlab/pipcompile.lock.txt`。
  astral 的 CI 构建路径（build_game.py/check_content.py/romfs_index.py）目前是纯标准库，
  登记 pip 锁前 dependency-scanning 无输入可扫，故与 container_scanning 一起放到下一 MR。
