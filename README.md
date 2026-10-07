# Xperia 1 V / XQ-DQ72 GUI2 recovery

为 Sony Xperia 1 V（pdx234 / XQ-DQ72）构建基于 Android 16 的 TWRP-Test LVGL / GUI2 recovery。
当前版本标识为 `final-logging-v1`，合入固定版本的 GUI2 PR #31，并包含 Sony 设备适配与日志控制修复。

## 功能与修复

- **日志开关**：在「设置 → 通用设置 → 日志记录」中提供「记录日志到 Metadata」，默认开启，选择会保存并在下次进入 recovery 时恢复。
- **解密输入**：支持自动、图案、PIN、密码输入类型选择；区分无法读取锁屏类型、Metadata 准备失败与用户凭据校验失败。
- **设置持久化**：修复 persist 挂载路径和设置文件读写，保存语言、主题及日志开关；恢复默认设置后写入持久化文件。
- **USB 存储与 SD 卡**：修正 SD 卡块设备和 configfs UMS 配置，检查 USB 存储启停结果，并在启用失败时保留挂载页面。
- **振动与服务兼容**：增加 Sony 振动 sysfs 后备实现，整合 QSEE、KeyMint、keystore2 与 recovery HIDL manifest 适配，以及旧厂商程序所需的 libbase ABI。
- **镜像封装检查**：在最终打包前恢复 recovery 专用 hwservicemanager，检查镜像中实际打包的 recovery、日志程序与共享库。

## Metadata 日志开关

入口：**设置 → 通用设置 → 日志记录 → 记录日志到 Metadata**。
英文界面名称为 **Settings → General Settings → Diagnostics → Save logs to Metadata**。

- 首次使用默认开启；旧设置文件没有此字段时也使用开启状态。
- 关闭后，后台日志程序停止向 `/metadata` 保存快照，退出 recovery 时也停止保存最终快照。
- 状态保存在 persist 的 TWRP 设置文件中；下次启动在访问 Metadata 前读取已保存的选择。
- 设置保存失败时回退界面状态；设置文件无效或无法读取时，后台程序等待 recovery 加载设置。
- 同一次启动中重新开启会继续当前日志目录；关闭开关后，已有日志仍保留。
- 此开关控制后台 Metadata 诊断日志；控制台及 `/tmp/recovery.log` 继续按 recovery 的临时日志逻辑运行。

自动日志目录为 `/metadata/XQ-DQ72-YARP/logs/`：

- `latest/`：当前记录日志的 recovery 启动，包括 recovery 日志、内核日志、logcat 和诊断状态。
- `previous/`：上一轮已记录日志的 recovery 启动。

可通过 recovery 文件管理器复制所需日志。分享日志前应检查其中的设备运行信息并脱敏。

## 使用 GitHub Actions 编译

1. 打开 **Actions → Build Xperia 1 V GUI2 recovery → Run workflow**。
2. 选择 `main` 分支；标准私有仓库 runner 建议保持 `jobs=2`，可选范围为 1–4。
3. 工作流先验证固定版本配置并测试日志开关，再同步源码、合入 GUI2、应用发布补丁和编译镜像。
4. 成功后下载 **Xperia-1V-XQ-DQ72-GUI2-final-<run-number>** artifact。

镜像 artifact 保留 30 天，包含：

- `recovery.img` 与 `SHA256SUMS`
- `recovery-header.txt`：镜像头、架构和大小检查结果
- `build-info.txt` 与 `source-manifest.xml`：构建配置版本及实际源码版本

运行结束时会尽可能上传 **Xperia-1V-build-logs-<run-number>-<run-attempt>** 诊断 artifact，保留 14 天。
当前流程直接报告失败并保存已有诊断，不再使用旧版等待修补脚本和多轮重编译机制。

推送构建配置、源码补丁或测试到 `main` 时自动执行快速验证；完整 Android 编译通过 **Run workflow** 手动发起。
仅更新 README 不会触发这条构建工作流。

## 源码与构建流程

本仓库保存构建脚本、固定版本依赖清单、源码补丁与设备覆盖文件；Android 平台源码在构建时从上游同步。

- `config/sources.env`：manifest、GUI2 和设备相关的固定提交。
- `manifests/final-platform.xml` 与 `config/source-remotes.json`：394 个固定版本依赖及公开源码地址；由 `scripts/materialize-manifest.py` 生成可同步 manifest。
- `patches/series.json` 与 `patches/*.patch`：六个源码组件的基准树、补丁校验和及修改后文件校验和。
- `overlays/`：日志程序、设备 init、SELinux、VINTF 和 recovery 配置。
- `scripts/`：源码同步、设备适配、资源保护、镜像编译与封装验证。
- `tests/logging-control-test.py`：默认开启、设置解析、关闭后停写、运行中暂停/恢复及重启记忆测试。

补丁覆盖 `bootable/recovery`、Sony pdx234 和 sm8550-common 设备树、`system/hwservicemanager`、`system/libbase` 与 `system/vold`。
构建时先合入固定版本 GUI2，再校验基准源码、应用补丁与覆盖文件、进行 Android 16 设备适配。
重复应用发布补丁会识别已完成状态，遇到非预期源码修改会停止。
Sony 厂商振动服务从固定版本上游获取并校验 SHA256，避免在本仓库重复存放二进制。

配置检查可单独运行：

```bash
python3 scripts/verify-project.py
```

在安装了 Python 3 和 GCC 的 Linux 环境中运行日志回归测试：

```bash
python3 tests/logging-control-test.py
```

测试使用临时目录和属性模拟，不挂载真实 Metadata 或 persist 分区。
完整编译流程见 [build-recovery.yml](.github/workflows/build-recovery.yml)。

## 构建资源与验证范围

工作流使用 Ubuntu 24.04 runner，默认 2 个编译任务、8 GiB 专用 swap、Soong Go 内存限制 6 GiB，任务超时为 6 小时。
源码同步使用 partial clone 与精简预编译工具链，保留 Sony 所需的 VNDK 31，并释放重复 Git blob。
编译过程记录磁盘、内存和 swap 状态，在资源接近耗尽或任务接近时限时提前停止以保存诊断。

镜像验证检查 Android v4 镜像头、100 MiB recovery 分区大小限制、LZ4 ramdisk、AArch64 GUI2 程序、fstab、日志控制以及关键服务和共享库的打包内容。
后台日志和设置解析已有主机回归测试；成功编译与镜像结构检查仍需配合 XQ-DQ72 真机验证启动、触摸、解密、USB 存储、振动和新增日志开关。

runner 使用通用构建身份完成本地 GUI2 合并，checkout 不保留仓库登录凭据；构建脚本无需用户 GitHub 登录信息。
构建过程仅在 runner 工作目录合入 GUI2，不向上游仓库推送或修改上游 PR。

## 上游项目

- [TWRP-Test/platform_manifest_twrp_aosp](https://github.com/TWRP-Test/platform_manifest_twrp_aosp)
- [GUI2 PR #31](https://github.com/TWRP-Test/android_bootable_recovery/pull/31)
- [Sony pdx234 设备树](https://github.com/sony-sm8550-TWRP/device_sony_pdx234-TWRP)
- [Sony sm8550-common 设备树](https://github.com/sony-sm8550-TWRP/device_sony_sm8550-common-TWRP)
