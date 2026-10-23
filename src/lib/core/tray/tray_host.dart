import 'dart:async';
import 'dart:io';

import 'package:tray_manager/legacy.dart';
import 'package:win32/win32.dart';
import 'package:win32_registry/win32_registry.dart';
import 'package:window_plus/window_plus.dart';

import '../../features/desktop/deskline_bridge.dart';

const int _allowShowMessage = WM_APP + 41;

class TrayHost with TrayListener {
  TrayHost._();

  static final TrayHost instance = TrayHost._();
  bool _ready = false;

  Future<void> start() async {
    if (_ready || !Platform.isWindows) return;
    final String? icon = _iconPath();
    if (icon == null) return;
    trayManager.addListener(this);
    _setPromoted(1);
    await trayManager.setIcon(icon);
    await trayManager.setToolTip('ReDeskLine');
    await trayManager.setContextMenu(
      Menu(
        items: [
          MenuItem(key: 'open', label: 'Open'),
          MenuItem.separator(),
          MenuItem(key: 'exit', label: 'Exit'),
        ],
      ),
    );
    await Future<void>.delayed(const Duration(milliseconds: 300));
    _setPromoted(1);
    trayManager.trayIcon?.setVisible(false);
    await Future<void>.delayed(const Duration(milliseconds: 200));
    trayManager.trayIcon?.setVisible(true);
    await trayManager.setIcon(icon);
    await trayManager.setToolTip('ReDeskLine');
    final PCWSTR traySettings = 'TraySettings'.toPcwstr();
    try {
      SendNotifyMessage(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        const WPARAM(0),
        LPARAM(traySettings.address),
      );
    } finally {
      free(traySettings);
    }
    _ready = true;
  }

  void _setPromoted(int value) {
    const String settings = r'Control Panel\NotifyIconSettings';
    final String exe = Platform.resolvedExecutable.toLowerCase();
    RegistryKey? root;
    try {
      root = CURRENT_USER.open(settings);
      for (final String name in root.keys) {
        final RegistryKey child = root.create(name);
        try {
          final String? target = child.getString('ExecutablePath');
          if (target == null || target.toLowerCase() != exe) continue;
          child.setValue('IsPromoted', RegistryValue.dword(value));
        } catch (_) {
          continue;
        } finally {
          child.close();
        }
      }
    } catch (_) {
      return;
    } finally {
      root?.close();
    }
  }

  Future<void> showWindow() async {
    if (_revealNativeWindow()) return;
    await WindowPlus.instance.show();
  }

  bool _revealNativeWindow() {
    final PCWSTR className = 'FLUTTER_RUNNER_WIN32_WINDOW'.toPcwstr();
    final PCWSTR title = 'ReDeskLine'.toPcwstr();
    try {
      final HWND hwnd = FindWindow(className, title).value;
      if (hwnd.address == 0) return false;
      SendMessage(hwnd, _allowShowMessage, const WPARAM(0), const LPARAM(0));
      return true;
    } finally {
      free(className);
      free(title);
    }
  }

  Future<void> quit() async {
    await DesklineBridge.instance.stop();
    await trayManager.destroy();
    await WindowPlus.instance.destroy();
  }

  @override
  void onTrayIconMouseDown() {
    unawaited(showWindow());
  }

  @override
  void onTrayMenuItemClick(MenuItem menuItem) {
    switch (menuItem.key) {
      case 'open':
        unawaited(showWindow());
      case 'exit':
        Timer.run(() => unawaited(quit()));
    }
  }

  String? _iconPath() {
    final Directory exeDir = File(Platform.resolvedExecutable).parent;
    final File beside = File('${exeDir.path}\\tray_icon.png');
    if (beside.existsSync()) return beside.path;
    Directory dir = exeDir;
    for (var depth = 0; depth < 8; depth++) {
      final File candidate = File(
        '${dir.path}\\src\\windows\\runner\\resources\\redeskline-icon.png',
      );
      if (candidate.existsSync()) return candidate.path;
      final Directory parent = dir.parent;
      if (parent.path == dir.path) break;
      dir = parent;
    }
    return null;
  }
}
