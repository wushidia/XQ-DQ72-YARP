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
私有仓库标准 runner 默认使用 2 个编译任务和 24 GiB swap，超时为 6 小时。
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
