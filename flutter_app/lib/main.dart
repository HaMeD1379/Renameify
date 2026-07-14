import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:window_manager/window_manager.dart';

import 'src/app_controller.dart';
import 'src/app_shell.dart';
import 'src/theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _configureDesktopWindow();
  runApp(const ProviderScope(child: RenameifyApp()));
}

Future<void> _configureDesktopWindow() async {
  if (!Platform.isWindows) {
    return;
  }

  try {
    await windowManager.ensureInitialized();
    const options = WindowOptions(
      size: Size(1280, 820),
      minimumSize: Size(1100, 680),
      center: true,
      backgroundColor: AppColors.black,
      title: 'Renameify',
    );
    windowManager.waitUntilReadyToShow(options, () async {
      await windowManager.show();
      await windowManager.focus();
    });
  } catch (_) {
    // Flutter tests and some CI hosts do not register desktop plugins.
  }
}

class RenameifyApp extends ConsumerWidget {
  const RenameifyApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    final appState = ref.watch(appControllerProvider);
    return MaterialApp.router(
      title: 'Renameify',
      debugShowCheckedModeBanner: false,
      theme: buildRenameifyTheme(Brightness.light),
      darkTheme: buildRenameifyTheme(Brightness.dark),
      themeMode: themeModeFromConfig(appState.config['ui_theme']),
      routerConfig: router,
    );
  }
}
