#include <windows.h>
#include <windowsx.h>
#include <shellapi.h>

#include <cstdlib>
#include <string>

namespace {

constexpr UINT kTrayCallback = WM_APP + 42;
constexpr UINT kAllowShow = WM_APP + 41;
constexpr UINT kQuitApp = WM_APP + 43;
constexpr UINT kTrayIconId = 1;
constexpr UINT kOverflowTimer = 77;
constexpr UINT kMenuOpen = 1;
constexpr UINT kMenuExit = 2;
constexpr wchar_t kHostClass[] = L"ReDeskLineTrayHost";

HWND g_host = nullptr;
HWND g_app = nullptr;
HANDLE g_parent = nullptr;
HICON g_icon = nullptr;
bool g_added = false;
UINT g_taskbar_created = 0;

HICON LoadAppIcon() {
  const int size = GetSystemMetrics(SM_CXSMICON);
  wchar_t path[MAX_PATH];
  if (GetModuleFileNameW(nullptr, path, MAX_PATH) > 0) {
    wchar_t* slash = wcsrchr(path, L'\\');
    if (slash != nullptr) {
      wcscpy_s(slash + 1, MAX_PATH - static_cast<size_t>(slash + 1 - path),
               L"ReDeskLine.ico");
      const HICON from_file = static_cast<HICON>(LoadImageW(
          nullptr, path, IMAGE_ICON, size, size,
          LR_LOADFROMFILE | LR_DEFAULTCOLOR));
      if (from_file != nullptr) {
        return from_file;
      }
    }
  }
  return LoadIconW(nullptr, IDI_APPLICATION);
}

NOTIFYICONDATAW MakeData() {
  NOTIFYICONDATAW data = {};
  data.cbSize = sizeof(data);
  data.hWnd = g_host;
  data.uID = kTrayIconId;
  data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP;
  data.uCallbackMessage = kTrayCallback;
  data.hIcon = g_icon;
  data.uVersion = NOTIFYICON_VERSION_4;
  wcscpy_s(data.szTip, L"ReDeskLine");
  return data;
}

void AddIcon() {
  if (g_host == nullptr) {
    return;
  }
  NOTIFYICONDATAW data = MakeData();
  Shell_NotifyIconW(NIM_DELETE, &data);
  if (Shell_NotifyIconW(NIM_ADD, &data) == TRUE) {
    Shell_NotifyIconW(NIM_SETVERSION, &data);
    g_added = true;
  }
}

void RemoveIcon() {
  if (!g_added || g_host == nullptr) {
    g_added = false;
    return;
  }
  NOTIFYICONDATAW data = MakeData();
  Shell_NotifyIconW(NIM_DELETE, &data);
  g_added = false;
}

void KeepInOverflow() {
  HKEY root = nullptr;
  if (RegOpenKeyExW(HKEY_CURRENT_USER, L"Control Panel\\NotifyIconSettings", 0,
                    KEY_READ, &root) != ERROR_SUCCESS) {
    return;
  }
  DWORD index = 0;
  wchar_t name[256];
  while (true) {
    DWORD name_length = 256;
    if (RegEnumKeyExW(root, index, name, &name_length, nullptr, nullptr,
                      nullptr, nullptr) != ERROR_SUCCESS) {
      break;
    }
    ++index;
    const std::wstring path =
        std::wstring(L"Control Panel\\NotifyIconSettings\\") + name;
    HKEY child = nullptr;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, path.c_str(), 0,
                      KEY_QUERY_VALUE | KEY_SET_VALUE,
                      &child) != ERROR_SUCCESS) {
      continue;
    }
    wchar_t target[MAX_PATH];
    DWORD size = sizeof(target);
    DWORD type = 0;
    const bool have_path =
        RegQueryValueExW(child, L"ExecutablePath", nullptr, &type,
                         reinterpret_cast<BYTE*>(target), &size) ==
            ERROR_SUCCESS &&
        type == REG_SZ;
    if (have_path) {
      const wchar_t* file = wcsrchr(target, L'\\');
      file = file == nullptr ? target : file + 1;
      if (_wcsicmp(file, L"ReDeskLine.exe") == 0 ||
          _wcsicmp(file, L"ReDeskLineTray.exe") == 0) {
        const DWORD promoted = 0;
        RegSetValueExW(child, L"IsPromoted", 0, REG_DWORD,
                       reinterpret_cast<const BYTE*>(&promoted),
                       sizeof(promoted));
      }
    }
    RegCloseKey(child);
  }
  RegCloseKey(root);
}

void ShowApp() {
  if (g_app != nullptr && IsWindow(g_app)) {
    PostMessageW(g_app, kAllowShow, 0, 0);
  }
}

void ExitApp() {
  if (g_app != nullptr && IsWindow(g_app)) {
    PostMessageW(g_app, kQuitApp, 0, 0);
  }
  RemoveIcon();
  PostQuitMessage(0);
}

void ShowMenu(int x, int y) {
  HMENU menu = CreatePopupMenu();
  if (menu == nullptr) {
    return;
  }
  AppendMenuW(menu, MF_STRING, kMenuOpen, L"Open");
  AppendMenuW(menu, MF_SEPARATOR, 0, nullptr);
  AppendMenuW(menu, MF_STRING, kMenuExit, L"Exit");

  SetForegroundWindow(g_host);
  const UINT command = static_cast<UINT>(TrackPopupMenu(
      menu,
      TPM_RIGHTALIGN | TPM_BOTTOMALIGN | TPM_RIGHTBUTTON | TPM_RETURNCMD |
          TPM_NONOTIFY,
      x, y, 0, g_host, nullptr));
  PostMessageW(g_host, WM_NULL, 0, 0);
  DestroyMenu(menu);

  if (command == kMenuOpen) {
    ShowApp();
  } else if (command == kMenuExit) {
    ExitApp();
  }
}

LRESULT CALLBACK HostProc(HWND hwnd, UINT message, WPARAM wparam,
                          LPARAM lparam) {
  if (g_taskbar_created != 0 && message == g_taskbar_created) {
    AddIcon();
    SetTimer(hwnd, kOverflowTimer, 400, nullptr);
    return 0;
  }
  if (message == WM_TIMER && wparam == kOverflowTimer) {
    KillTimer(hwnd, kOverflowTimer);
    KeepInOverflow();
    return 0;
  }
  if (message == WM_CLOSE) {
    RemoveIcon();
    DestroyWindow(hwnd);
    return 0;
  }
  if (message == WM_DESTROY) {
    PostQuitMessage(0);
    return 0;
  }
  if (message != kTrayCallback) {
    return DefWindowProcW(hwnd, message, wparam, lparam);
  }

  const UINT event = LOWORD(lparam);
  POINT cursor = {GET_X_LPARAM(wparam), GET_Y_LPARAM(wparam)};
  if (cursor.x == 0 && cursor.y == 0) {
    GetCursorPos(&cursor);
  }
  switch (event) {
    case NIN_SELECT:
    case NIN_KEYSELECT:
    case WM_LBUTTONUP:
    case WM_LBUTTONDBLCLK:
      ShowApp();
      break;
    case WM_CONTEXTMENU:
    case WM_RBUTTONUP:
    case WM_RBUTTONDOWN:
      ShowMenu(cursor.x, cursor.y);
      break;
    default:
      break;
  }
  return 0;
}

void ParseArgs(HWND* app, DWORD* parent_pid) {
  int argc = 0;
  wchar_t** argv = CommandLineToArgvW(GetCommandLineW(), &argc);
  if (argv == nullptr) {
    return;
  }
  for (int i = 1; i < argc; ++i) {
    if (wcsncmp(argv[i], L"--hwnd=", 7) == 0) {
      *app = reinterpret_cast<HWND>(
          static_cast<ULONG_PTR>(std::wcstoull(argv[i] + 7, nullptr, 10)));
    } else if (wcsncmp(argv[i], L"--pid=", 6) == 0) {
      *parent_pid = static_cast<DWORD>(wcstoul(argv[i] + 6, nullptr, 10));
    }
  }
  LocalFree(argv);
}

}  // namespace

int APIENTRY wWinMain(HINSTANCE instance, HINSTANCE, wchar_t*, int) {
  HANDLE mutex = CreateMutexW(nullptr, TRUE, L"Local\\ReDeskLineTray");
  if (mutex != nullptr && GetLastError() == ERROR_ALREADY_EXISTS) {
    HWND existing = FindWindowW(kHostClass, nullptr);
    if (existing != nullptr) {
      PostMessageW(existing, WM_CLOSE, 0, 0);
      Sleep(200);
    }
    CloseHandle(mutex);
    mutex = CreateMutexW(nullptr, TRUE, L"Local\\ReDeskLineTray");
  }

  DWORD parent_pid = 0;
  ParseArgs(&g_app, &parent_pid);
  if (parent_pid != 0) {
    g_parent = OpenProcess(SYNCHRONIZE, FALSE, parent_pid);
  }
  g_icon = LoadAppIcon();
  g_taskbar_created = RegisterWindowMessageW(L"TaskbarCreated");

  WNDCLASSW wc = {};
  wc.lpfnWndProc = HostProc;
  wc.hInstance = instance;
  wc.lpszClassName = kHostClass;
  wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
  RegisterClassW(&wc);

  g_host = CreateWindowExW(WS_EX_TOOLWINDOW, kHostClass, L"ReDeskLine",
                           WS_POPUP, 0, 0, 0, 0, nullptr, nullptr, instance,
                           nullptr);
  if (g_host == nullptr) {
    return 1;
  }

  AddIcon();
  SetTimer(g_host, kOverflowTimer, 400, nullptr);

  MSG msg = {};
  while (true) {
    const DWORD wait = MsgWaitForMultipleObjects(
        g_parent != nullptr ? 1 : 0, g_parent != nullptr ? &g_parent : nullptr,
        FALSE, INFINITE, QS_ALLINPUT);
    if (g_parent != nullptr && wait == WAIT_OBJECT_0) {
      RemoveIcon();
      break;
    }
    while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
      if (msg.message == WM_QUIT) {
        RemoveIcon();
        if (g_icon != nullptr) {
          DestroyIcon(g_icon);
        }
        if (g_parent != nullptr) {
          CloseHandle(g_parent);
        }
        if (mutex != nullptr) {
          CloseHandle(mutex);
        }
        return 0;
      }
      TranslateMessage(&msg);
      DispatchMessageW(&msg);
    }
  }

  RemoveIcon();
  if (g_icon != nullptr) {
    DestroyIcon(g_icon);
  }
  if (g_parent != nullptr) {
    CloseHandle(g_parent);
  }
  if (mutex != nullptr) {
    CloseHandle(mutex);
  }
  return 0;
}
