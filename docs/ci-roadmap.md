# CI 门禁与后续验收

配置包含内容守卫、无游戏资源单元测试、真实 Linux runtime 静态库构建、密钥扫描、
Semgrep、Advanced SAST、基于真实编译数据库的 C/C++ 扫描、SDK 容器扫描、依赖扫描和
SBOM 覆盖检查。所有适用安全作业均不允许失败；配置存在不等于当前提交已经通过，
交付时应检查精确 HEAD 及合并后 main 的实际流水线结果。

SDK 固定为 `native-games/toolchain:02b1aa2ee13b00c30b38`，容器扫描读取项目 23
登记的同版本通用包并核验完整摘要。三份 Python 清单共同生成哈希锁；门禁核对直接
依赖版本和全部已解析依赖的 SBOM，不能以两份手写锁相同代替完整性检查。
实现与维护命令见 [.gitlab/README.md](../.gitlab/README.md)。

执行仅限获准远端 Mac mini / Intel Mac 的对应 Runner；日用 Mac 只编辑与编排。
构建、测试、扫描和作业存储收尾分别验收，终态作业的有效证据交付后清理临时内容。

公开 CI 只构建不需要游戏资源的 runtime。完整游戏 AOT、Linux 依赖打包、Deck 启动、
ASTC 画面、输入/QTE、三级触屏栏、Amiibo、金手指及长时稳定性属于后续私有验收，
不因此处绿色而标为完成；当前 `hardware_validated=false`。
