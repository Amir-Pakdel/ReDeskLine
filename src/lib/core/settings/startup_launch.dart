import 'dart:io';

import 'package:win32_registry/win32_registry.dart';

import '../services/win_registry_service.dart';

const _runKey = r'Software\Microsoft\Windows\CurrentVersion\Run';
const _runName = 'ReDeskLine';

class StartupLaunch {
  static Future<bool> isEnabled() async {
    final ProcessResult result = await Process.run('schtasks', ['/Query', '/TN', _runName]);
    return result.exitCode == 0;
  }

  static Future<bool> setEnabled(bool on) async {
    await WinRegistryService.deleteValue(CURRENT_USER, _runKey, _runName);
    if (!on) {
      final ProcessResult result = await Process.run('schtasks', ['/Delete', '/TN', _runName, '/F']);
      return result.exitCode == 0 || _taskMissing(result);
    }

    final String exe = Platform.resolvedExecutable.replaceAll("'", "''");
    final ProcessResult result = await Process.run('powershell.exe', [
      '-NoProfile',
      '-NonInteractive',
      '-ExecutionPolicy',
      'Bypass',
      '-Command',
      """
\$action = New-ScheduledTaskAction -Execute '$exe' -Argument '--background'
\$trigger = New-ScheduledTaskTrigger -AtLogOn -User \$env:USERNAME
\$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
\$principal = New-ScheduledTaskPrincipal -UserId \$env:USERNAME -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName '$_runName' -Action \$action -Trigger \$trigger -Settings \$settings -Principal \$principal -Force | Out-Null
""",
    ]);
    return result.exitCode == 0;
  }

  static bool _taskMissing(ProcessResult result) {
    final String text = '${result.stdout}\n${result.stderr}'.toLowerCase();
    return text.contains('cannot find') || text.contains('does not exist');
  }
}
