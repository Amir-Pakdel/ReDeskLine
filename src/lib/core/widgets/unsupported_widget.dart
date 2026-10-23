import 'package:fluent_ui/fluent_ui.dart';
import 'package:window_plus/window_plus.dart';

class const UnsupportedWidget({super.key}) extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return ScaffoldPage(
      content: ContentDialog(
        title: const Text('Error'),
        content: const Text(
          'This Windows is too old. ReDeskLine runs on Windows 10, Windows 11, and Windows Server 2016 or newer, including Home, Pro, Enterprise, and Education.',
        ),
        actions: [
          Button(child: const Text('OK'), onPressed: () async => WindowPlus.instance.close()),
        ],
      ),
    );
  }
}
