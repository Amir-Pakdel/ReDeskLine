#include <flutter/dart_project.h>
#include <flutter/flutter_view_controller.h>
#include <windows.h>

#include "flutter_window.h"
#include "utils.h"

int APIENTRY wWinMain(_In_ HINSTANCE instance, _In_opt_ HINSTANCE prev,
                      _In_ wchar_t *command_line, _In_ int show_command) {
  // Attach to console when present (e.g., 'flutter run') or create a
  // new console when running with a debugger.
  if (!::AttachConsole(ATTACH_PARENT_PROCESS) && ::IsDebuggerPresent()) {
    CreateAndAttachConsole();
  }

  // Initialize COM, so that it is available for use in the library and/or
  // plugins.
  ::CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

  flutter::DartProject project(L"data");

  // TODO: Remove this. flutter/flutter/issues/178916
  // This forces Flutter to use a separate thread for Dart.
  // This mode will be removed in a future version of Flutter.
  project.set_ui_thread_policy(flutter::UIThreadPolicy::RunOnSeparateThread);

  std::vector<std::string> command_line_arguments =
      GetCommandLineArguments();
  bool start_in_background = false;
  for (const std::string& argument : command_line_arguments) {
    if (argument == "--background") {
      start_in_background = true;
    }
  }

  project.set_dart_entrypoint_arguments(std::move(command_line_arguments));
  g_suppress_show = start_in_background;

  FlutterWindow window(project);
  Win32Window::Point origin(10, 10);
  Win32Window::Size size(1280, 720);
  if (!window.Create(L"ReDeskLine", origin, size)) {
    return g_activated_existing ? EXIT_SUCCESS : EXIT_FAILURE;
  }
  window.SetQuitOnClose(true);
  if (start_in_background) {
    ShowWindow(window.GetHandle(), SW_HIDE);
  }

  ::MSG msg;
  while (::GetMessage(&msg, nullptr, 0, 0)) {
    ::TranslateMessage(&msg);
    ::DispatchMessage(&msg);
  }

  ::CoUninitialize();
  return EXIT_SUCCESS;
}
