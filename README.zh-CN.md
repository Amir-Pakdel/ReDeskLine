[English](README.md) | [فارسی](README.fa.md) | [Русский](README.ru.md) | **中文**

<div align="center">

# ReDeskLine

在任意版本的 Windows 10 和 Windows 11 上自定义桌面。

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Author-Amir%20Pakdel-111111)](https://github.com/Amir-Pakdel)

</div>

ReDeskLine 是 **Amir Pakdel** 开发的本地 Windows 桌面定制工具。Fluent 界面应用与后台桌面引擎合并为一个程序，可统一管理壁纸、任务栏、光标、小组件和系统优化。

支持 Windows 10、Windows 11 以及 Windows Server 2016 或更新版本。Home、Pro、Enterprise、Education、IoT 和 Server 使用同一应用。

## 功能

- **桌面工作室** — 动态壁纸、任务栏效果、光标轨迹和小部件
- **优化与调整** — 安全、性能、个性化、实用工具和 Windows Update 控制
- **Microsoft Store** — 搜索、下载、安装和卸载应用包
- **系统托盘** — 关闭窗口后进入通知区域；右键可选择 **Open** 或 **Exit**
- **开机启动** — 在后台保持运行，不打开窗口
- **语言** — 英语、波斯语以及其他内置翻译

设置和桌面引擎数据保存在 `%LOCALAPPDATA%\Deskline`。

## 安装

1. 运行 `ReDeskLine-Setup.exe`。
2. 选择安装目录。
3. 启动 **ReDeskLine**。部分调整需要管理员权限，因此 Windows 会弹出 UAC。

关闭窗口会将应用隐藏到托盘。要完全退出，请在托盘图标上选择 **Exit**。

## 从源码构建

需要 Flutter SDK、与原生桥接兼容的 Rust 工具链；若要制作安装包，还需要 Inno Setup。

```bat
cd src
flutter pub get
flutter build windows --release
```

发布文件位于 `src\build\windows\x64\runner\Release\ReDeskLine.exe`。`inno-setup.iss` 用于打包安装程序。

## 许可

ReDeskLine 采用 [GNU General Public License v3.0](LICENSE) 许可。

**Copyright (C) 2026 Amir Pakdel。** 名称 **ReDeskLine** 以及本版权声明必须保留在本软件的所有副本及实质性部分中。详见 [NOTICE](NOTICE)。

ReDeskLine 包含源自 [Revision Tool](https://github.com/meetrevision/revision-tool)（GPL-3.0）的代码以及 Deskline 引擎。

同时包含：

- [Fluent System Icons](https://github.com/microsoft/fluentui-system-icons)（Microsoft）— MIT

## 作者

**Amir Pakdel** — [github.com/Amir-Pakdel](https://github.com/Amir-Pakdel)
