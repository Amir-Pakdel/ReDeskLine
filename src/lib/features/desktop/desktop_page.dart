import 'package:fluent_ui/fluent_ui.dart';
import 'package:fluentui_system_icons/fluentui_system_icons.dart' as msicons;
import 'package:go_router/go_router.dart';

import '../../core/widgets/card_highlight.dart';
import '../../extensions.dart';
import '../../utils_gui.dart';
import 'deskline_bridge.dart';
import 'studio_page.dart';

class const DesktopPage({super.key}) extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return ScaffoldPage.scrollable(
      padding: kScaffoldPagePadding,
      children: [
        Text(DesklineBridge.instance.message),
        for (final kind in StudioKind.values)
          CardHighlight(
            icon: kind.icon,
            label: kind.title,
            description: kind.description,
            onPressed: () => context.push('/desktop/${kind.name}'),
            action: const ChevronRightAction(),
          ),
      ].withSpacing(5),
    );
  }
}

extension on StudioKind {
  IconData get icon => switch (this) {
    StudioKind.wallpaper => msicons.FluentIcons.image_20_regular,
    StudioKind.taskbar => msicons.FluentIcons.dock_20_regular,
    StudioKind.cursor => msicons.FluentIcons.cursor_20_regular,
    StudioKind.widgets => msicons.FluentIcons.grid_20_regular,
    StudioKind.audio => msicons.FluentIcons.speaker_2_20_regular,
    StudioKind.windows => msicons.FluentIcons.color_20_regular,
    StudioKind.retro => msicons.FluentIcons.history_20_regular,
    StudioKind.game => msicons.FluentIcons.games_20_regular,
    StudioKind.tools => msicons.FluentIcons.wrench_20_regular,
    StudioKind.pc => msicons.FluentIcons.desktop_20_regular,
    StudioKind.network => msicons.FluentIcons.wifi_1_20_regular,
    StudioKind.drivers => msicons.FluentIcons.developer_board_20_regular,
    StudioKind.cleanup => msicons.FluentIcons.broom_20_regular,
  };
}
