#ifndef RUNNER_TRAY_ICON_H_
#define RUNNER_TRAY_ICON_H_

#include <windows.h>

// Starts a medium-integrity helper that owns the notification icon so Explorer
// can show it in Show hidden icons and deliver Open / Exit clicks.
class TrayIcon {
 public:
  static TrayIcon& Instance();

  void Install(HWND flutter_hwnd);
  void Remove();
  bool Handle(HWND hwnd, UINT message, WPARAM wparam, LPARAM lparam);

 private:
  void AllowExplorerMessages(HWND hwnd);
  void StopHelper();
  bool StartHelper();
  bool LaunchUnelevated(wchar_t* command_line, const wchar_t* exe);

  HWND flutter_hwnd_ = nullptr;
  HANDLE helper_process_ = nullptr;
};

#endif  // RUNNER_TRAY_ICON_H_
