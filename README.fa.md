[English](README.md) | **فارسی** | [Русский](README.ru.md) | [中文](README.zh-CN.md)

<div align="center">

# ReDeskLine

ویندوز ۱۰ و ویندوز ۱۱ را در هر نسخه‌ای شخصی‌سازی کنید.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Author-Amir%20Pakdel-111111)](https://github.com/Amir-Pakdel)

</div>

ReDeskLine یک سفارشی‌ساز دسکتاپ ویندوز است که **امیر پاکدل** ساخته است. یک برنامه با ظاهر Fluent با موتور دسکتاپ پس‌زمینه ترکیب شده تا والپیپر، نوار وظیفه، نشانگر، ویجت‌ها و بهینه‌سازی‌های سیستم از یک برنامه کنترل شوند.

روی ویندوز ۱۰، ویندوز ۱۱ و Windows Server 2016 یا جدیدتر اجرا می‌شود. نسخه‌های Home، Pro، Enterprise، Education، IoT و Server از همان برنامه استفاده می‌کنند.

## قابلیت‌ها

- **استودیوی دسکتاپ** — والپیپر زنده، افکت نوار وظیفه، دنباله نشانگر و ویجت‌ها
- **بهینه‌سازی و تنظیمات** — امنیت، عملکرد، شخصی‌سازی، ابزارها و کنترل Windows Update
- **Microsoft Store** — جستجو، دانلود، نصب و حذف بسته‌ها
- **سینی سیستم** — با بستن پنجره به ناحیه اعلان می‌رود؛ راست‌کلیک **Open** یا **Exit**
- **اجرا هنگام روشن شدن ویندوز** — در پس‌زمینه فعال می‌ماند و پنجره باز نمی‌شود
- **زبان‌ها** — انگلیسی، فارسی و چند ترجمه دیگر

تنظیمات و داده موتور دسکتاپ در `%LOCALAPPDATA%\Deskline` ذخیره می‌شوند.

## نصب

1. فایل `ReDeskLine-Setup.exe` را اجرا کنید.
2. پوشه نصب را انتخاب کنید.
3. **ReDeskLine** را باز کنید. ویندوز اجازه مدیر می‌خواهد چون بعضی تنظیمات به آن نیاز دارند.

بستن پنجره برنامه را به سینی می‌فرستد. برای خروج کامل از آیکون سینی **Exit** را بزنید.

## ساخت از روی منبع

نیازمندی‌ها: Flutter SDK، Rust سازگار با پل native، و در صورت نیاز Inno Setup.

```bat
cd src
flutter pub get
flutter build windows --release
```

خروجی در `src\build\windows\x64\runner\Release\ReDeskLine.exe` است. اسکریپت `inno-setup.iss` همان خروجی را بسته می‌کند.

## مجوز

ReDeskLine تحت [GNU General Public License v3.0](LICENSE) منتشر می‌شود.

**Copyright (C) 2026 Amir Pakdel.** نام **ReDeskLine** و این اعلام کپی‌رایت باید در همه نسخه‌ها و بخش‌های عمده نرم‌افزار حفظ شود. [NOTICE](NOTICE) را ببینید.

ReDeskLine شامل کار مشتق‌شده از [Revision Tool](https://github.com/meetrevision/revision-tool) (GPL-3.0) و موتور Deskline است.

همچنین شامل:

- [Fluent System Icons](https://github.com/microsoft/fluentui-system-icons) از Microsoft — MIT

## نویسنده

**امیر پاکدل (Amir Pakdel)** — [github.com/Amir-Pakdel](https://github.com/Amir-Pakdel)
