# CI 资产与验证边界

本目录复用两塞尔达的扫描资产，并按 Astral Chain 的构建方式适配。

- `prepare_cpp_scan.py` 从真实 runtime 构建的编译数据库提取 C/C++ 翻译单元，
  复制并重映射 SDK 头；`unpack_cpp_scan.py` / `run_cpp_scan.py` 检查实际扫描覆盖率。
- `fetch_toolchain.rb` 按 `toolchain.env` 下载本项目的通用包，核验完整 SHA-256。
  当前固定为实际构建使用的 `02b1aa2ee13b00c30b38`，不是 TOTK 的另一套 SDK。
  `run_container_scan.rb` 保留完整诊断、漏洞报告和 SBOM，失败不能被日志管道吞掉。
- `generate_scan_lock.sh` 合并三份真实依赖清单：`tools/requirements.txt`、
  `tools/requirements-installer.txt`、`tools/requirements-py314.txt`。
  使用 Python 3.12、pip 26.3、pip-tools 7.6.2 真实解析版本，再由
  `generate_scan_lock.py` 从 PyPI 官方 HTTPS 版本元数据获取各平台安装包的摘要，生成
  `.gitlab/pipcompile.lock.txt`。这不代表已下载或运行所有平台安装包；安装时仍须核验摘要。
  维护命令只在获准远端的固定 Linux/Python 3.12 SDK 容器执行。脚本在
  `out/dependency-lock/` 新建独立会话目录，pip 工具、缓存和临时输入统一放入其中，
  退出时清理，最终哈希锁保留在仓库；不会向宿主或 SDK 全局安装工具。
- `check_dependency_coverage.py` 拒绝遗漏清单、版本冲突、无摘要锁文件以及未支持的语法。
  扫描后逐包核对 SBOM，范围包含锁中的传递依赖；缺包、错版本或缺 SBOM 都使 CI 失败。

Python 3.12 的解析锁用于扫描统一依赖清单，不代表 Windows/Python 3.14 环境已实测。
按 [GitLab 已有解析锁的配置路线](https://docs.gitlab.com/user/application_security/dependency_scanning/migration_guide_to_sbom_based_scans/)，
`disabled_resolution_jobs: python` 仅避免模板再次解析并覆盖既有锁；实际依赖漏洞扫描和
SBOM 覆盖门禁继续强制失败。模板解析作业默认允许失败，不能把它误计为强制安全门禁。
锁文件保留固定扫描器要求的第二行 pip-compile 标记，并复制到清单所在的
`tools/pipcompile.lock.txt`。`DS_ENABLE_MANIFEST_FALLBACK=false` 禁止解析失败后静默退回
只扫描直接依赖。标记要求见 [GitLab 固定扫描器源码](https://gitlab.com/gitlab-org/security-products/analyzers/dependency-scanning/-/blob/cd0ebcc7e66002d96711bddf9d8e6b5047d6adf3/scanner/common/common.go)。
容器扫描覆盖 SDK 系统与语言依赖；源码扫描和 CI 成功均不能证明零漏洞或游戏实机可玩。
游戏资源、密钥、派生代码及私有包不进入公开仓库或普通 CI 制品。
