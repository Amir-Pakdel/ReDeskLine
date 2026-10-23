[English](README.md) | [فارسی](README.fa.md) | **Русский** | [中文](README.zh-CN.md)

<div align="center">

# ReDeskLine

Персонализация Windows 10 и Windows 11 на любой редакции.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Author-Amir%20Pakdel-111111)](https://github.com/Amir-Pakdel)

</div>

ReDeskLine — локальный настройщик рабочего стола Windows от **Amir Pakdel**. Приложение с интерфейсом Fluent и фоновый движок рабочего стола объединены в одну программу: обои, панель задач, курсор, виджеты и системные твики.

Работает в Windows 10, Windows 11 и Windows Server 2016 или новее. Home, Pro, Enterprise, Education, IoT и Server используют одно и то же приложение.

## Возможности

- **Desktop studio** — живые обои, эффекты панели задач, след курсора и виджеты
- **Твики и оптимизация** — безопасность, производительность, оформление, утилиты и Windows Update
- **Microsoft Store** — поиск, загрузка, установка и удаление пакетов
- **Системный трей** — закрытие окна прячет программу в область уведомлений; правый щелчок: **Open** или **Exit**
- **Запуск при включении** — программа остается в фоне и не открывает окно
- **Языки** — английский, персидский и другие встроенные переводы

Настройки и данные движка хранятся в `%LOCALAPPDATA%\Deskline`.

## Установка

1. Запустите `ReDeskLine-Setup.exe`.
2. Выберите папку установки.
3. Откройте **ReDeskLine**. Windows запросит права администратора: часть твиков без них недоступна.

Закрытие окна скрывает приложение в трей. Полный выход — пункт **Exit** у значка в трее.

## Сборка из исходников

Нужны Flutter SDK, Rust для нативного моста и Inno Setup, если нужен установщик.

```bat
cd src
flutter pub get
flutter build windows --release
```

Готовый файл: `src\build\windows\x64\runner\Release\ReDeskLine.exe`. Скрипт `inno-setup.iss` собирает установщик.

## Лицензия

ReDeskLine распространяется на условиях [GNU General Public License v3.0](LICENSE).

**Copyright (C) 2026 Amir Pakdel.** Имя **ReDeskLine** и это уведомление об авторском праве должны сохраняться во всех копиях и существенных частях программы. См. [NOTICE](NOTICE).

ReDeskLine включает производную работу от [Revision Tool](https://github.com/meetrevision/revision-tool) (GPL-3.0) и движок Deskline.

Также включено:

- [Fluent System Icons](https://github.com/microsoft/fluentui-system-icons) от Microsoft — MIT

## Автор

**Amir Pakdel** — [github.com/Amir-Pakdel](https://github.com/Amir-Pakdel)
