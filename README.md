# Xperia 1 V / XQ-DQ72 GUI2 recovery

此仓库通过 GitHub Actions 为 Sony Xperia 1 V（pdx234 / XQ-DQ72）构建
TWRP-Test LVGL recovery，并在 Actions 的源码工作目录中合入 GUI2 PR #31。

- Manifest: [TWRP-Test/platform_manifest_twrp_aosp, lvgl](https://github.com/TWRP-Test/platform_manifest_twrp_aosp/tree/lvgl)
- GUI2: [android_bootable_recovery PR #31](https://github.com/TWRP-Test/android_bootable_recovery/pull/31)
- Device: [sony-sm8550-TWRP/device_sony_pdx234-TWRP](https://github.com/sony-sm8550-TWRP/device_sony_pdx234-TWRP)
- Common: [sony-sm8550-TWRP/device_sony_sm8550-common-TWRP](https://github.com/sony-sm8550-TWRP/device_sony_sm8550-common-TWRP)

源码固定版本见 `config/sources.env` 和 `manifests/sony.xml`。
构建不向任何上游仓库推送、不关闭或合并上游 PR。

在 **Actions → Build Xperia 1 V GUI2 recovery → Run workflow** 启动编译。
私有仓库标准 runner 默认使用 2 个编译任务，源码同步及编译期间使用 8 GiB 专用 swap，Soong Go 内存限制为 6 GiB，超时为 6 小时。
下载成功运行中的 **Xperia-1V-XQ-DQ72-GUI2** artifact，包含：

- `recovery.img` 及 `SHA256SUMS`
- 实际源码版本、合并 commit 和完整解析后的 manifest
- 镜像头及分区大小检查结果

失败运行仍上传同步/编译日志和设备树调整 patch。
原始 Sony 设备树使用 Android 12.1 分支；此仓库的脚本将其适配至指定的
Android 16 manifest。成功编译和镜像结构验证不能代替 XQ-DQ72 真机的
启动、触摸、解密和其他功能测试。

整个工作流的源码同步、PR 合入、构建及产物保存都发生在 GitHub runner；
提交此配置时不需要本地 checkout 或下载镜像。

构建失败时会立即上传对应 attempt 的 diagnostics artifact，并保留同一 runner
等待最多 45 分钟。提交 `repairs/<run-id>/attempt-<下次序号>.sh` 后，runner
会仅从此仓库读取并执行修补脚本，然后继续编译（最多 8 次）。这套流程使用
只读仓库 token 获取修补文件；编译步骤不接收该 token。

为适应标准 runner 磁盘容量，同步使用 partial clone；Clang、Rust、JDK
仅检出本次构建对应的 Linux 工具链。保留 Sony 设备所用 VNDK 31，
移除其余 VNDK 快照与模拟器预编译文件。

同步阶段在磁盘余量低于 5 GiB 时会提前停止并保存诊断日志；源码检出后，
释放预编译文件的重复 Git blob 缓存（保留提交、目录元数据和工作目录文件），
确保 Actions runner 与编译输出有可用空间。

检出以 4 个项目为一批；每批成功后立即释放工作目录中已有文件的重复 Git blob，
提交和目录元数据继续保留。已完成批次记录在 runner，磁盘保护触发后可在同一
runner 提交 `repairs/<run-id>/attempt-source-2.sh` 等修补文件后继续检出。
CTS 仅保留公共构建配置和库，Linux 构建不检出 macOS 工具链。

编译每分钟记录可用磁盘、内存、swap 和占用内存最多的进程；在磁盘低于
4 GiB，或内存与 swap 接近耗尽时提前停止以保存诊断。源码准备完成后会单独
上传包含完整 manifest 的诊断 artifact，便于 runner 意外中断后追踪版本。

Sony 预编译显示库所需的 Qualcomm HIDL 接口额外取自固定版本的
LineageOS `android_vendor_qcom_opensource_interfaces`。旧的独立 QCOM 解密包
由 Android 16 recovery/vold 的解密实现替代；保留 Sony 原有的 QTI boot HAL 文件。
镜像验证检查 v4 镜像头、100 MiB 分区限制、LZ4 ramdisk、ARM64 recovery
可执行程序、recovery fstab 和 GUI2 显示实现。
