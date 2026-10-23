import 'dart:convert';
import 'dart:io';

import 'package:fluent_ui/fluent_ui.dart';

import '../../core/widgets/card_highlight.dart';
import '../../extensions.dart';
import '../../utils_gui.dart';
import 'deskline_bridge.dart';

enum StudioKind {
  wallpaper,
  taskbar,
  cursor,
  widgets,
  audio,
  windows,
  retro,
  game,
  tools,
  pc,
  network,
  drivers,
  cleanup;

  String get title => switch (this) {
    wallpaper => 'Wallpaper',
    taskbar => 'Taskbar',
    cursor => 'Cursor',
    widgets => 'Widgets',
    audio => 'Audio',
    windows => 'Windows',
    retro => 'Retro',
    game => 'Game Boost',
    tools => 'Tools',
    pc => 'PC Check',
    network => 'Network',
    drivers => 'Drivers',
    cleanup => 'Cleanup',
  };

  String get description => switch (this) {
    wallpaper => 'Video, web page, or pattern behind the desktop icons.',
    taskbar => 'Accent, shape, dock, and scroll-to-change volume.',
    cursor => 'Trails, click effects, and a replacement pointer.',
    widgets => 'Clock, monitor, music, notes, and the start list.',
    audio => 'Click sounds, ambience, and the equalizer block.',
    windows => 'Accent color, light and dark schedule, classic menu.',
    retro => 'Left taskbar, compact taskbar, and transparency.',
    game => 'Pause effects and raise priority for a fullscreen app.',
    tools => 'Keep the PC awake, and the topmost hotkey.',
    pc => 'A short sample of this PC.',
    network => 'Gateway, adapters, and a ping.',
    drivers => 'Display driver age and problem devices.',
    cleanup => 'Temporary files, dumps, reports, and the Recycle Bin.',
  };
}

enum _Kind { toggle, number, choice, text }

class _Field {
  const _Field(
    this.section,
    this.key,
    this.label, {
    this.help,
    this.kind = _Kind.toggle,
    this.min = 0,
    this.max = 100,
    this.fallback = 0,
    this.choices = const [],
  });

  final String section;
  final String key;
  final String label;
  final String? help;
  final _Kind kind;
  final int min;
  final int max;
  final int fallback;
  final List<(String, String)> choices;
}

class const StudioPage({super.key, required this.kind}) extends StatefulWidget {
  final StudioKind kind;

  @override
  State<StudioPage> createState() => _StudioPageState();
}

class _StudioPageState extends State<StudioPage> {
  String _report = '';
  bool _busy = false;
  List<Map<String, dynamic>> _library = [];
  List<Map<String, dynamic>> _cleanup = [];

  DesklineBridge get _bridge => DesklineBridge.instance;

  @override
  void initState() {
    super.initState();
    if (widget.kind == StudioKind.wallpaper) {
      _refreshLibrary();
    }
  }

  List<_Field> get _fields => switch (widget.kind) {
    StudioKind.wallpaper => _wallpaperFields,
    StudioKind.taskbar => _taskbarFields,
    StudioKind.cursor => _cursorFields,
    StudioKind.widgets => _widgetFields,
    StudioKind.audio => _audioFields,
    StudioKind.windows => _windowsFields,
    StudioKind.retro => _retroFields,
    StudioKind.game => _gameFields,
    StudioKind.tools => _toolFields,
    _ => const [],
  };

  Future<void> _set(String section, String key, Object? value) async {
    await _bridge.update(section, {key: value});
    if (mounted) setState(() {});
  }

  Future<void> _run(String name, [List<String> args = const []]) async {
    setState(() {
      _busy = true;
      _report = 'Working…';
    });
    final result = await _bridge.command(name, args);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _report = const JsonEncoder.withIndent('  ').convert(result);
    });
    if (widget.kind == StudioKind.wallpaper) await _refreshLibrary();
    if (widget.kind == StudioKind.cleanup && result is List) {
      _cleanup = [for (final item in result) Map<String, dynamic>.from(item as Map)];
    }
  }

  Future<void> _refreshLibrary() async {
    final result = await _bridge.command('list-wallpapers');
    if (!mounted || result is! List) return;
    setState(() {
      _library = [for (final item in result) Map<String, dynamic>.from(item as Map)];
    });
  }

  Future<void> _importWallpaper() async {
    final path = await _pickMedia();
    if (path == null || path.isEmpty) return;
    await _run('import-wallpaper', [path]);
  }

  @override
  Widget build(BuildContext context) {
    final bridge = _bridge;
    return ScaffoldPage.scrollable(
      padding: kScaffoldPagePadding,
      children: [
        Text(widget.kind.description),
        for (final field in _fields) _editor(bridge, field),
        ..._actions(),
        if (_report.isNotEmpty)
          CardHighlight(label: 'Result', description: _report, initiallyExpanded: true),
      ].withSpacing(8),
    );
  }

  Widget _editor(DesklineBridge bridge, _Field field) {
    final section = bridge.section(field.section);
    final value = section[field.key];
    return switch (field.kind) {
      _Kind.toggle => CardListTile(
        title: field.label,
        description: field.help,
        trailing: CardToggleSwitch(
          value: value == true,
          onChanged: (next) => _set(field.section, field.key, next),
        ),
      ),
      _Kind.number => _NumberField(
        label: field.label,
        help: field.help,
        min: field.min,
        max: field.max,
        value: value is num ? value.round() : field.fallback,
        onChanged: (next) => _set(field.section, field.key, next),
      ),
      _Kind.choice => CardListTile(
        title: field.label,
        description: field.help,
        trailing: ComboBox<String>(
          value: field.choices.any((item) => item.$1 == '$value')
              ? '$value'
              : field.choices.first.$1,
          items: [
            for (final choice in field.choices)
              ComboBoxItem(value: choice.$1, child: Text(choice.$2)),
          ],
          onChanged: (next) {
            if (next != null) _set(field.section, field.key, next);
          },
        ),
      ),
      _Kind.text => _TextField(
        label: field.label,
        help: field.help,
        value: '${value ?? ''}',
        onSubmitted: (next) => _set(field.section, field.key, next),
      ),
    };
  }

  List<Widget> _actions() {
    if (_busy) return const [Text('Working…')];
    return switch (widget.kind) {
      StudioKind.wallpaper => [
        Row(
          children: [
            Button(onPressed: _importWallpaper, child: const Text('Import')),
            const SizedBox(width: 8),
            Button(onPressed: () => _run('remove-wallpaper'), child: const Text('Remove')),
          ],
        ),
        for (final entry in _library)
          CardListTile(
            title: '${entry['name'] ?? 'Wallpaper'}',
            trailing: Button(
              child: const Text('Use'),
              onPressed: () => _run('select-wallpaper', ['${entry['id']}']),
            ),
          ),
      ],
      StudioKind.retro => [
        Button(onPressed: () => _run('restart-explorer'), child: const Text('Restart Explorer')),
      ],
      StudioKind.audio => [_EqBands(onChanged: (bands) => _set('audio', 'eq_bands', bands))],
      StudioKind.game => [
        Button(
          onPressed: () => _run('add-power-plan'),
          child: const Text('Add high-performance plan'),
        ),
      ],
      StudioKind.pc => [Button(onPressed: () => _run('pc-check'), child: const Text('Run check'))],
      StudioKind.network => [
        Button(onPressed: () => _run('network'), child: const Text('Check network')),
      ],
      StudioKind.drivers => [
        Button(onPressed: () => _run('drivers'), child: const Text('Check drivers')),
      ],
      StudioKind.cleanup => [
        Button(
          onPressed: () async {
            await _run('cleanup-scan');
          },
          child: const Text('Scan'),
        ),
        for (final category in _cleanup)
          CardListTile(
            title: '${category['title'] ?? ''}',
            description: '${category['detail'] ?? ''} · ${category['bytes'] ?? 0} bytes',
            trailing: Button(
              child: const Text('Delete'),
              onPressed: () => _run('cleanup-delete', ['${category['id']}']),
            ),
          ),
      ],
      _ => const [],
    };
  }
}

class _NumberField extends StatefulWidget {
  const _NumberField({
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
    this.help,
  });

  final String label;
  final String? help;
  final int value;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;

  @override
  State<_NumberField> createState() => _NumberFieldState();
}

class _NumberFieldState extends State<_NumberField> {
  late double _value = widget.value.toDouble();

  @override
  void didUpdateWidget(_NumberField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.value != widget.value) _value = widget.value.toDouble();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('${widget.label} · ${_value.round()}'),
        if (widget.help != null) Text(widget.help!),
        Slider(
          min: widget.min.toDouble(),
          max: widget.max.toDouble(),
          value: _value.clamp(widget.min, widget.max).toDouble(),
          onChanged: (next) => setState(() => _value = next),
          onChangeEnd: (next) => widget.onChanged(next.round()),
        ),
      ],
    );
  }
}

class _TextField extends StatefulWidget {
  const _TextField({
    required this.label,
    required this.value,
    required this.onSubmitted,
    this.help,
  });

  final String label;
  final String? help;
  final String value;
  final ValueChanged<String> onSubmitted;

  @override
  State<_TextField> createState() => _TextFieldState();
}

class _TextFieldState extends State<_TextField> {
  late final TextEditingController _controller = TextEditingController(text: widget.value);

  @override
  void didUpdateWidget(_TextField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.value != widget.value && _controller.text != widget.value) {
      _controller.text = widget.value;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(widget.label),
        if (widget.help != null) Text(widget.help!),
        TextBox(controller: _controller, onSubmitted: widget.onSubmitted),
      ],
    );
  }
}

Future<String?> _pickMedia() async {
  const script = r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = "Media|*.mp4;*.webm;*.mkv;*.mov;*.avi;*.gif;*.png;*.jpg;*.jpeg;*.webp;*.bmp"
if ($dialog.ShowDialog() -eq "OK") { $dialog.FileName }
''';
  final result = await Process.run('powershell', ['-NoProfile', '-Command', script]);
  final path = result.stdout.toString().trim();
  if (path.isEmpty) return null;
  return path;
}

class _EqBands extends StatelessWidget {
  const _EqBands({required this.onChanged});

  final ValueChanged<List<int>> onChanged;

  static const _labels = ['31', '62', '125', '250', '500', '1k', '2k', '4k', '8k', '16k'];

  @override
  Widget build(BuildContext context) {
    final raw = DesklineBridge.instance.section('audio')['eq_bands'];
    final bands = <int>[
      for (var index = 0; index < 10; index++)
        raw is List && index < raw.length && raw[index] is num ? (raw[index] as num).round() : 0,
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('10-band equalizer'),
        for (var index = 0; index < 10; index++)
          _NumberField(
            label: '${_labels[index]} Hz',
            min: -12,
            max: 12,
            value: bands[index],
            onChanged: (next) {
              final copy = [...bands];
              copy[index] = next;
              onChanged(copy);
            },
          ),
      ],
    );
  }
}

const _wallpaperFields = <_Field>[
  _Field('wallpaper', 'enabled', 'Play on the desktop'),
  _Field(
    'wallpaper',
    'source',
    'Source',
    kind: _Kind.choice,
    choices: [('media', 'Video'), ('web', 'Web page'), ('shader', 'Pattern')],
  ),
  _Field('wallpaper', 'url', 'Web address', kind: _Kind.text, help: 'https://'),
  _Field(
    'wallpaper',
    'shader',
    'Pattern',
    kind: _Kind.choice,
    choices: [('plasma', 'Plasma'), ('waves', 'Waves'), ('grid', 'Grid'), ('bars', 'Bars')],
  ),
  _Field('wallpaper', 'muted', 'Mute', help: 'On keeps the wallpaper silent.'),
  _Field('wallpaper', 'hide_icons', 'Hide desktop icons'),
  _Field('wallpaper', 'slideshow', 'Slideshow'),
  _Field(
    'wallpaper',
    'slideshow_minutes',
    'Slideshow interval',
    kind: _Kind.choice,
    choices: [('1', '1 min'), ('5', '5 min'), ('10', '10 min'), ('30', '30 min')],
  ),
  _Field('wallpaper', 'all_monitors', 'Span monitors'),
  _Field('wallpaper', 'pause_battery', 'Pause on battery'),
  _Field('wallpaper', 'pause_apps', 'Pause for these programs', kind: _Kind.text),
  _Field('wallpaper', 'idle_screensaver', 'Idle screensaver'),
  _Field(
    'wallpaper',
    'idle_minutes',
    'Idle minutes',
    kind: _Kind.number,
    min: 1,
    max: 30,
    fallback: 5,
  ),
  _Field('wallpaper', 'blur', 'Blur', kind: _Kind.number),
  _Field('wallpaper', 'brightness', 'Brightness', kind: _Kind.number, min: -100, max: 0),
  _Field(
    'wallpaper',
    'overlay',
    'Overlay',
    kind: _Kind.choice,
    choices: [
      ('none', 'None'),
      ('dust', 'Dust'),
      ('snow', 'Snow'),
      ('stars', 'Stars'),
      ('embers', 'Embers'),
      ('mist', 'Mist'),
      ('rain', 'Rain'),
      ('sparks', 'Sparks'),
      ('fog', 'Fog'),
    ],
  ),
  _Field('wallpaper', 'overlay_amount', 'Overlay amount', kind: _Kind.number, fallback: 50),
  _Field('wallpaper', 'overlay_color', 'Overlay tint', kind: _Kind.text),
];

const _taskbarFields = <_Field>[
  _Field('taskbar', 'enabled', 'Animated taskbar'),
  _Field('taskbar', 'clear', 'Clear the Windows taskbar'),
  _Field(
    'taskbar',
    'design',
    'Design',
    kind: _Kind.choice,
    choices: [
      ('wave', 'Wave'),
      ('pulse', 'Pulse'),
      ('aurora', 'Aurora'),
      ('ember', 'Ember'),
      ('glass', 'Glass'),
    ],
  ),
  _Field('taskbar', 'height', 'Height', kind: _Kind.number, fallback: 100),
  _Field('taskbar', 'side_gap', 'Side gap', kind: _Kind.number),
  _Field('taskbar', 'corners', 'Corners', kind: _Kind.number),
  _Field('taskbar', 'brightness', 'Brightness', kind: _Kind.number, min: -100, max: 0),
  _Field('taskbar', 'show_bar', 'Center bar'),
  _Field('taskbar', 'bar_width', 'Bar width', kind: _Kind.number, fallback: 40),
  _Field('taskbar', 'bar_height', 'Bar height', kind: _Kind.number, fallback: 100),
  _Field('taskbar', 'bar_radius', 'Bar radius', kind: _Kind.number),
  _Field('taskbar', 'bar_opacity', 'Bar opacity', kind: _Kind.number, fallback: 55),
  _Field(
    'taskbar',
    'bar_mode',
    'Bar mode',
    kind: _Kind.choice,
    choices: [('cover', 'Cover'), ('invert', 'Invert')],
  ),
  _Field(
    'taskbar',
    'bar_color',
    'Bar color',
    kind: _Kind.choice,
    choices: [('black', 'Black'), ('white', 'White')],
  ),
  _Field(
    'taskbar',
    'accent',
    'Windows material',
    kind: _Kind.choice,
    choices: [('clear', 'Clear'), ('blur', 'Blur'), ('acrylic', 'Acrylic'), ('opaque', 'Opaque')],
  ),
  _Field(
    'taskbar',
    'dynamic_maximized',
    'When a window is maximized',
    kind: _Kind.choice,
    choices: [
      ('same', 'Same'),
      ('normal', 'Normal'),
      ('clear', 'Clear'),
      ('blur', 'Blur'),
      ('acrylic', 'Acrylic'),
    ],
  ),
  _Field('taskbar', 'accent_color', 'Tint', kind: _Kind.text),
  _Field('taskbar', 'accent_opacity', 'Tint strength', kind: _Kind.number, fallback: 40),
  _Field('taskbar', 'shape_margin', 'Edge margin', kind: _Kind.number, max: 40),
  _Field('taskbar', 'shape_radius', 'Real corners', kind: _Kind.number, max: 24),
  _Field('taskbar', 'dock', 'Dock and center the taskbar'),
  _Field(
    'taskbar',
    'dock_width',
    'Dock width',
    kind: _Kind.number,
    min: 20,
    max: 100,
    fallback: 60,
  ),
  _Field('taskbar', 'scroll_volume', 'Scroll on the taskbar changes volume'),
  _Field(
    'taskbar',
    'scroll_percent',
    'Volume step',
    kind: _Kind.choice,
    choices: [('1', '1%'), ('2', '2%'), ('5', '5%'), ('10', '10%')],
  ),
  _Field('taskbar', 'hide_maximized', 'Hide on maximized windows'),
  _Field('taskbar', 'gif', 'Taskbar GIF path', kind: _Kind.text),
];

const _cursorFields = <_Field>[
  _Field('cursor', 'enabled', 'Trails and click effects'),
  _Field('cursor', 'color', 'Color', kind: _Kind.text),
  _Field(
    'cursor',
    'mode',
    'Color mode',
    kind: _Kind.choice,
    choices: [('single', 'Single'), ('gradient', 'Gradient'), ('rainbow', 'Rainbow')],
  ),
  _Field(
    'cursor',
    'move',
    'Trail',
    kind: _Kind.choice,
    choices: [
      ('classic', 'Classic'),
      ('glow', 'Glow'),
      ('sparks', 'Sparks'),
      ('stardust', 'Stardust'),
      ('none', 'None'),
    ],
  ),
  _Field(
    'cursor',
    'left_click',
    'Left click',
    kind: _Kind.choice,
    choices: [
      ('shockwave', 'Shockwave'),
      ('ripple', 'Ripple'),
      ('burst', 'Burst'),
      ('none', 'None'),
    ],
  ),
  _Field(
    'cursor',
    'right_click',
    'Right click',
    kind: _Kind.choice,
    choices: [
      ('same', 'Same as left'),
      ('shockwave', 'Shockwave'),
      ('ripple', 'Ripple'),
      ('burst', 'Burst'),
      ('none', 'None'),
    ],
  ),
  _Field('cursor', 'amount', 'Amount', kind: _Kind.number, fallback: 50),
  _Field('cursor', 'size', 'Size', kind: _Kind.number, fallback: 50),
  _Field('cursor', 'length', 'Length', kind: _Kind.number, fallback: 50),
  _Field('cursor', 'glow', 'Glow', kind: _Kind.number, fallback: 55),
  _Field('cursor', 'spread', 'Spread', kind: _Kind.number, fallback: 50),
  _Field(
    'cursor',
    'pointer',
    'Pointer',
    kind: _Kind.choice,
    choices: [
      ('system', 'System'),
      ('ring', 'Ring'),
      ('cross', 'Cross'),
      ('dot', 'Dot'),
      ('arrow', 'Arrow'),
    ],
  ),
  _Field('cursor', 'pointer_gif', 'Pointer GIF path', kind: _Kind.text),
];

const _widgetFields = <_Field>[
  _Field('widgets', 'clock', 'Clock'),
  _Field('widgets', 'monitor', 'Monitor'),
  _Field('widgets', 'music', 'Now playing'),
  _Field('widgets', 'games', 'Games'),
  _Field('widgets', 'disk', 'Disk'),
  _Field('widgets', 'net', 'Network'),
  _Field('widgets', 'notes', 'Notes'),
  _Field('widgets', 'launch', 'Start menu list'),
  _Field('widgets', 'locked', 'Lock widget positions'),
  _Field('widgets', 'hour24', '24-hour clock'),
  _Field('widgets', 'seconds', 'Seconds'),
  _Field('widgets', 'weekday', 'Weekday'),
  _Field('widgets', 'show_date', 'Date'),
  _Field('widgets', 'uppercase', 'Uppercase'),
  _Field('widgets', 'notes_text', 'Notes text', kind: _Kind.text),
  _Field('widgets', 'launch_query', 'Filter the start list', kind: _Kind.text),
];

const _audioFields = <_Field>[
  _Field('audio', 'keyboard', 'Keyboard sounds'),
  _Field('audio', 'mouse', 'Mouse sounds'),
  _Field('audio', 'key_volume', 'Key volume', kind: _Kind.number, fallback: 70),
  _Field('audio', 'mouse_volume', 'Mouse volume', kind: _Kind.number, fallback: 50),
  _Field('audio', 'scape', 'Soundscape'),
  _Field('audio', 'scape_volume', 'Soundscape volume', kind: _Kind.number, fallback: 40),
  _Field('audio', 'rain', 'Rain', kind: _Kind.number),
  _Field('audio', 'wind', 'Wind', kind: _Kind.number),
  _Field('audio', 'birds', 'Birds', kind: _Kind.number),
  _Field('audio', 'city', 'City', kind: _Kind.number),
  _Field('audio', 'thunder', 'Thunder', kind: _Kind.number),
  _Field('audio', 'plug_chime', 'Chime when power is plugged in'),
  _Field('audio', 'sound_pack', 'Sound pack folder', kind: _Kind.text),
  _Field('audio', 'eq', 'Equalizer APO block'),
  _Field('audio', 'eq_bass', 'Bass', kind: _Kind.number, min: -12, max: 12),
  _Field('audio', 'eq_mid', 'Mid', kind: _Kind.number, min: -12, max: 12),
  _Field('audio', 'eq_treble', 'Treble', kind: _Kind.number, min: -12, max: 12),
  _Field('audio', 'key_file', 'Custom key sound', kind: _Kind.text),
  _Field('audio', 'mouse_file', 'Custom mouse sound', kind: _Kind.text),
];

const _windowsFields = <_Field>[
  _Field('windows', 'accent', 'Accent color', kind: _Kind.text),
  _Field('windows', 'schedule', 'Schedule light and dark'),
  _Field('windows', 'light_from', 'Light from', kind: _Kind.text),
  _Field('windows', 'dark_from', 'Dark from', kind: _Kind.text),
  _Field('windows', 'classic_menu', 'Classic context menu'),
];

const _retroFields = <_Field>[
  _Field('retro', 'left_taskbar', 'Taskbar on the left'),
  _Field('retro', 'compact_taskbar', 'Compact taskbar'),
  _Field('retro', 'glass', 'Transparency'),
];

const _gameFields = <_Field>[
  _Field('game', 'enabled', 'Game Boost'),
  _Field('game', 'max_performance', 'Switch to the performance power plan'),
  _Field('game', 'priority', 'Raise the game priority'),
  _Field('game', 'pause_effects', 'Pause wallpaper and effects'),
];

const _toolFields = <_Field>[
  _Field('tools', 'awake', 'Keep the PC awake'),
  _Field('tools', 'awake_minutes', 'Minutes', kind: _Kind.number, min: 1, max: 240, fallback: 60),
  _Field('tools', 'awake_screen', 'Keep the screen on'),
  _Field('tools', 'hotkey', 'Win+Ctrl+T toggles topmost'),
];
