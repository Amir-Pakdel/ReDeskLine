import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// Talks to the Deskline effect engine that lives inside this app.
class DesklineBridge {
  DesklineBridge._();

  static final DesklineBridge instance = DesklineBridge._();

  Process? _process;
  bool _stopping = false;
  int _restarts = 0;
  String message = 'Desktop effects start with ReDeskLine.';

  Directory? get root {
    final starts = <Directory>[Directory.current, File(Platform.resolvedExecutable).parent];
    for (final start in starts) {
      var dir = start;
      for (var depth = 0; depth < 8; depth++) {
        final candidate = Directory('${dir.path}${Platform.pathSeparator}deskline');
        if (File('${candidate.path}${Platform.pathSeparator}engine.py').existsSync()) {
          return candidate;
        }
        final parent = dir.parent;
        if (parent.path == dir.path) break;
        dir = parent;
      }
    }
    return null;
  }

  File get _configFile {
    final base = Platform.environment['LOCALAPPDATA'] ?? Directory.systemTemp.path;
    return File('$base${Platform.pathSeparator}Deskline${Platform.pathSeparator}config.json');
  }

  File get _stopFile {
    final base = Platform.environment['LOCALAPPDATA'] ?? Directory.systemTemp.path;
    return File('$base${Platform.pathSeparator}Deskline${Platform.pathSeparator}engine.stop');
  }

  String? get _pythonw {
    final folder = root;
    if (folder == null) return null;
    final local = File(
      '${folder.path}${Platform.pathSeparator}.venv${Platform.pathSeparator}Scripts${Platform.pathSeparator}pythonw.exe',
    );
    if (local.existsSync()) return local.path;
    final profile = Platform.environment['USERPROFILE'];
    if (profile == null) return null;
    final sibling = File(
      '$profile${Platform.pathSeparator}Desktop${Platform.pathSeparator}Deskline${Platform.pathSeparator}.venv${Platform.pathSeparator}Scripts${Platform.pathSeparator}pythonw.exe',
    );
    if (sibling.existsSync()) return sibling.path;
    return null;
  }

  String? get _python {
    final pythonw = _pythonw;
    if (pythonw == null) return null;
    return pythonw.replaceFirst('pythonw.exe', 'python.exe');
  }

  Map<String, dynamic> readConfig() {
    try {
      final raw = jsonDecode(_configFile.readAsStringSync());
      if (raw is Map<String, dynamic>) return raw;
      if (raw is Map) return raw.map((key, value) => MapEntry('$key', value));
    } on Object {
      // A missing file means the engine has not saved defaults yet.
    }
    return <String, dynamic>{};
  }

  Map<String, dynamic> section(String name) {
    final value = readConfig()[name];
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return value.map((key, item) => MapEntry('$key', item));
    return <String, dynamic>{};
  }

  Future<void> update(String name, Map<String, Object?> values) async {
    final data = readConfig();
    final current = section(name);
    current.addAll(values);
    data[name] = current;
    await _configFile.parent.create(recursive: true);
    await _configFile.writeAsString(const JsonEncoder.withIndent('  ').convert(data));
  }

  void _log(String text) {
    try {
      final file = File(
        '${_configFile.parent.path}${Platform.pathSeparator}bridge.log',
      );
      file.parent.createSync(recursive: true);
      file.writeAsStringSync('${DateTime.now().toIso8601String()} $text\n', mode: FileMode.append);
    } on Object {
      // Logging must not block the window.
    }
  }

  Future<void> start() async {
    final current = _process;
    if (current != null) {
      try {
        final code = await current.exitCode.timeout(Duration.zero);
        _log('previous engine already exited $code');
        _process = null;
      } on TimeoutException {
        message = 'Desktop effects are running in ReDeskLine.';
        return;
      }
    }
    _stopping = false;
    final Directory? folder = root;
    final String? pythonw = _pythonw;
    if (folder == null || pythonw == null) {
      message = 'Deskline engine was not found next to ReDeskLine.';
      _log(message);
      return;
    }
    if (_stopFile.existsSync()) _stopFile.deleteSync();
    _log('start $pythonw in ${folder.path}');
    final Process process = await Process.start(
      pythonw,
      ['engine.py'],
      workingDirectory: folder.path,
      mode: ProcessStartMode.normal,
    );
    _process = process;
    message = 'Desktop effects are running in ReDeskLine.';
    process.stderr.listen((bytes) => _log('stderr ${utf8.decode(bytes, allowMalformed: true)}'));
    unawaited(
      process.exitCode.then((code) async {
        _log('engine exit $code');
        if (!identical(_process, process) || _stopping) return;
        _process = null;
        if (code != 0 && _restarts < 3) {
          _restarts += 1;
          await Future<void>.delayed(const Duration(seconds: 1));
          if (!_stopping) await start();
        }
      }),
    );
  }

  Future<void> stop() async {
    _stopping = true;
    final Process? process = _process;
    if (process == null) return;
    await _stopFile.parent.create(recursive: true);
    await _stopFile.writeAsString('stop');
    try {
      await process.exitCode.timeout(const Duration(seconds: 2));
    } on TimeoutException {
      process.kill();
    }
    _process = null;
  }

  Future<Object?> command(String name, [List<String> args = const []]) async {
    final folder = root;
    final python = _python;
    if (folder == null || python == null) {
      return {'ok': false, 'error': 'Python for Deskline was not found.'};
    }
    final result = await Process.run(
      python,
      ['-m', 'deskline.commands', name, ...args],
      workingDirectory: folder.path,
      stdoutEncoding: utf8,
      stderrEncoding: utf8,
    );
    final text = result.stdout.toString().trim();
    if (text.isEmpty) {
      return {'ok': false, 'error': result.stderr.toString().trim()};
    }
    try {
      return jsonDecode(text);
    } on FormatException {
      return {'ok': false, 'error': text};
    }
  }
}
