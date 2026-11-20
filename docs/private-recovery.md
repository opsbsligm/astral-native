# 个人恢复

源码与私有加密恢复包分别保存。源码可以分享；自己提供的游戏转储、密钥和录制数据保存在本项目私有 Generic Packages 的 `private-recovery` 中，不进入 Git 历史或公共 CI。

重置 Deck 前，先在别处保留 age identity 文件；解密密钥不能只放在将被重置的 Deck，也不上传到 GitLab。`age` 1.2.1 及以上是恢复工具的前置依赖，identity 与接收者文件路径由使用者传入，不写进仓库。GitLab 下载令牌用仅当前账户可读的 0600 文件。

`age` 默认从 `PATH` 查找。刚重置的 Deck 通常只在项目自有目录里放着 `age`，为此可以把 `NATIVE_AGE` 指向该二进制（绝对路径，或仍按 `PATH` 解析的裸程序名）；版本门槛与包格式都不变。

## 封装什么

有三种可恢复形态，选一种即可，工具按恢复出来的目录结构决定走哪条路，不需要额外开关：

- 发行包（推荐）：`--include runtime=<seal_private_package.py 的输出目录>`。恢复后 `run.sh --verify` 原地校验，不需要编译器、不需要 Docker，几分钟就能重新开玩。
- 完整构建输入：`--include dump=<含 base.nsp、update-1.0.1.nsp、prod.keys 的目录>`，并按下节补 `answers`。恢复后走 `docs/building.md` 的提取、提升、编译、打包全链。
- 只备份录制数据：最小集合，见下。

`shader-answers.bin` 是玩出来的记录，不是构建产物：`tools/prepare_shaders.py` 靠它预生成着色器种子（`seed-answers.bin`／`seed-programs.bin`），删掉之后重建出的包会在游戏里现编着色器，表现为卡顿。它只存在于运行目录，务必单独留存并封装：

```sh
python3 tools/recovery.py seal --label ASTRAL_VERSION \
  --include dump=/mnt/my-inputs --include answers=/mnt/my-recordings \
  --recipients /private/age-recipients.txt --destination /mnt/sealed-bundle
```

`seal` 只读取输入，输入变化、符号链接或非普通文件都会被拒绝，加密清单含逐文件摘要与执行位。`rebuild_private.py` 在重建路径上找不到 `shader-answers.bin` 会直接停止，不会交出一个会卡顿的包。

## 发布与重建

```sh
python3 tools/recovery_gitlab.py publish --url https://www.bsligm.com:8445 \
  --project 23 --version MY_PACKAGE_VERSION --token-file /private/gitlab-token \
  --bundle /mnt/sealed-bundle
```

发布逐分片回读校验，下载再次核对摘要，恢复最后核对加密清单；部分备份必须用 `--missing` 明示缺项，重建遇缺项停止，不把不完整资源当可玩包。

在 x86_64 Linux 主机上重建（发行包路径约需 32 GiB 可用，完整输入路径需 160 GiB）：

```sh
python3 tools/rebuild_private.py --version MY_PACKAGE_VERSION \
  --token-file /private/gitlab-token --identity /private/age-identity.txt \
  --work /mnt/native-restore
```

输出目录必须是新目录，不覆盖已有安装或存档。密文分片可放另一块盘或已挂载的 NAS，用 `--encrypted-work` 指定新目录；只有位于不同文件系统才真正分摊峰值，同盘换目录不增加可用空间。空间紧张时 `seal`／`restore`／`rebuild_private.py` 都支持 `--low-peak`：封装不生成整份 `payload.age`，还原先完整认证一遍再流式解包，每遍重核对分片摘要，两遍都通过才原子安装。

## 已验证到什么程度

- 恢复工具链（`recovery.py`／`recovery_gitlab.py`）与两塞尔达同版本，`tests/recovery_test.py`、`tests/recovery_stream_test.py` 在 CI 内执行。
- `rebuild_private.py` 的两条分支由单元测试覆盖发行包路径（识别 `run.sh` 并原地校验、不触发重建）；完整输入路径按 `docs/building.md` 串接现有工具，尚未在干净主机端到端跑通，真机重建未验收。
- age identity 与既有恢复包的可用性已在受控主机上以真实解密验证；本项目尚未产出首个 `private-recovery` 包，封装与发布流程沿用两塞尔达已跑通的命令。
