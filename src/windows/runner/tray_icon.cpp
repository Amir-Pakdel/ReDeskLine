#include "tray_icon.h"

#include <shellapi.h>

#include <string>

#include "win32_window.h"

namespace {

constexpr wchar_t kHostClass[] = L"ReDeskLineTrayHost";

void WriteEngineStop() {
  wchar_t local_app_data[MAX_PATH];
  const DWORD length =
      GetEnvironmentVariableW(L"LOCALAPPDATA", local_app_data, MAX_PATH);
  if (length == 0 || length >= MAX_PATH) {
    return;
  }
  const std::wstring directory = std::wstring(local_app_data) + L"\\Deskline";
  CreateDirectoryW(directory.c_str(), nullptr);
  const HANDLE file = CreateFileW(
      (directory + L"\\engine.stop").c_str(), GENERIC_WRITE, 0, nullptr,
      CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (file != INVALID_HANDLE_VALUE) {
    CloseHandle(file);
  }
}

}  // namespace

TrayIcon& TrayIcon::Instance() {
  static TrayIcon icon;
  return icon;
}

void TrayIcon::AllowExplorerMessages(HWND hwnd) {
  if (hwnd == nullptr) {
    return;
  }
  const UINT messages[] = {
      kReDeskLineAllowShow, kReDeskLineQuit, WM_CONTEXTMENU, WM_COMMAND, WM_APP,
  };
  for (const UINT message : messages) {
    ChangeWindowMessageFilterEx(hwnd, message, MSGFLT_ALLOW, nullptr);
  }
}

void TrayIcon::Install(HWND flutter_hwnd) {
  flutter_hwnd_ = flutter_hwnd;
  AllowExplorerMessages(flutter_hwnd_);
  StopHelper();
  StartHelper();
}

void TrayIcon::Remove() {
  StopHelper();
  flutter_hwnd_ = nullptr;
}

bool TrayIcon::Handle(HWND hwnd, UINT message, WPARAM, LPARAM) {
  if (hwnd != flutter_hwnd_) {
    return false;
  }
  if (message == kReDeskLineQuit) {
    WriteEngineStop();
    StopHelper();
    DestroyWindow(hwnd);
    return true;
  }
  return false;
}

void TrayIcon::StopHelper() {
  HWND helper = FindWindowW(kHostClass, nullptr);
  if (helper != nullptr) {
    PostMessageW(helper, WM_CLOSE, 0, 0);
  }
  if (helper_process_ != nullptr) {
    if (WaitForSingleObject(helper_process_, 400) == WAIT_TIMEOUT) {
      TerminateProcess(helper_process_, 0);
    }
    CloseHandle(helper_process_);
    helper_process_ = nullptr;
  }
}

bool TrayIcon::LaunchUnelevated(wchar_t* command_line, const wchar_t* exe) {
  HWND shell = GetShellWindow();
  DWORD pid = 0;
  if (shell != nullptr) {
    GetWindowThreadProcessId(shell, &pid);
  }
  HANDLE process = nullptr;
  if (pid != 0) {
    process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (process == nullptr) {
      process = OpenProcess(PROCESS_QUERY_INFORMATION, FALSE, pid);
    }
  }
  HANDLE token = nullptr;
  if (process != nullptr) {
    OpenProcessToken(process, TOKEN_DUPLICATE, &token);
    CloseHandle(process);
  }
  HANDLE primary = nullptr;
  if (token != nullptr) {
    DuplicateTokenEx(token,
                     TOKEN_ASSIGN_PRIMARY | TOKEN_DUPLICATE | TOKEN_QUERY |
                         TOKEN_ADJUST_DEFAULT | TOKEN_ADJUST_SESSIONID,
                     nullptr, SecurityImpersonation, TokenPrimary, &primary);
    CloseHandle(token);
  }
  STARTUPINFOW si = {};
  si.cb = sizeof(si);
  si.dwFlags = STARTF_USESHOWWINDOW;
  si.wShowWindow = SW_HIDE;
  PROCESS_INFORMATION pi = {};
  BOOL created = FALSE;
  if (primary != nullptr) {
    created = CreateProcessWithTokenW(primary, 0, exe, command_line,
                                      CREATE_UNICODE_ENVIRONMENT, nullptr,
                                      nullptr, &si, &pi);
    CloseHandle(primary);
  }
  if (!created) {
    created = CreateProcessW(exe, command_line, nullptr, nullptr, FALSE,
                             CREATE_UNICODE_ENVIRONMENT, nullptr, nullptr, &si,
                             &pi);
  }
  if (!created) {
    return false;
  }
  CloseHandle(pi.hThread);
  helper_process_ = pi.hProcess;
  return true;
}

bool TrayIcon::StartHelper() {
  if (flutter_hwnd_ == nullptr) {
    return false;
  }
  wchar_t exe[MAX_PATH];
  if (GetModuleFileNameW(nullptr, exe, MAX_PATH) == 0) {
    return false;
  }
  wchar_t* slash = wcsrchr(exe, L'\\');
  if (slash == nullptr) {
    return false;
  }
  wcscpy_s(slash + 1, MAX_PATH - static_cast<size_t>(slash + 1 - exe),
           L"ReDeskLineTray.exe");
  if (GetFileAttributesW(exe) == INVALID_FILE_ATTRIBUTES) {
    return false;
  }

  wchar_t command[MAX_PATH + 80];
  swprintf_s(command, L"\"%s\" --hwnd=%llu --pid=%lu", exe,
             static_cast<unsigned long long>(
                 reinterpret_cast<ULONG_PTR>(flutter_hwnd_)),
             GetCurrentProcessId());
  return LaunchUnelevated(command, exe);
}
