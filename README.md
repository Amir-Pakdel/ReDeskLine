**English** | [فارسی](README.fa.md) | [Русский](README.ru.md) | [中文](README.zh-CN.md)

<div align="center">

# ReDeskLine

Personalize Windows 10 and Windows 11, on any edition.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Author-Amir%20Pakdel-111111)](https://github.com/Amir-Pakdel)

</div>

ReDeskLine is a local Windows desktop customizer by **Amir Pakdel**. It combines a Fluent Windows app with a background desktop engine so you can change wallpaper, taskbar, cursor, widgets, and system tweaks from one program.

It runs on Windows 10, Windows 11, and Windows Server 2016 or newer. Home, Pro, Enterprise, Education, IoT, and Server editions use the same app.

## Features

- **Desktop studio** — live wallpaper, taskbar effects, cursor trails, and widgets
- **Tweaks & optimizations** — security, performance, personalization, utilities, and Windows Update controls
- **Microsoft Store** — search, download, install, and remove packages
- **System tray** — close to the notification area; right-click **Open** or **Exit**
- **Start on boot** — stay active in the background without opening the window
- **Languages** — English, Persian, and other bundled translations

Settings and desktop-engine data live under `%LOCALAPPDATA%\Deskline`.

## Install

1. Run `ReDeskLine-Setup.exe`.
2. Choose the install folder.
3. Launch **ReDeskLine**. Windows will ask for administrator permission because some tweaks need it.

Closing the window hides the app to the tray. Use **Exit** on the tray icon to quit completely.

## Build from source

Requirements: Flutter SDK, a Rust toolchain compatible with the native bridge, and Inno Setup if you want an installer.

```bat
cd src
flutter pub get
flutter build windows --release
```

The release binary is written to `src\build\windows\x64\runner\Release\ReDeskLine.exe`. The Inno Setup script `inno-setup.iss` packages that output.

## License

ReDeskLine is licensed under the [GNU General Public License v3.0](LICENSE).

**Copyright (C) 2026 Amir Pakdel.** The name **ReDeskLine** and this copyright notice must be preserved in all copies and substantial portions of the software. See [NOTICE](NOTICE).

ReDeskLine includes work derived from [Revision Tool](https://github.com/meetrevision/revision-tool) (GPL-3.0) and the included Deskline engine.

It also contains:

- [Fluent System Icons](https://github.com/microsoft/fluentui-system-icons) by Microsoft — MIT

## Author

**Amir Pakdel** — [github.com/Amir-Pakdel](https://github.com/Amir-Pakdel)
