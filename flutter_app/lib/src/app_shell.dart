import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'app_controller.dart';
import 'models.dart';
import 'pages.dart';
import 'theme.dart';

final appRouterProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/scan',
    routes: [
      ShellRoute(
        builder:
            (context, state, child) =>
                RenameifyShell(location: state.uri.path, child: child),
        routes: [
          GoRoute(path: '/scan', builder: (_, __) => const ScanPage()),
          GoRoute(path: '/review', builder: (_, __) => const ReviewPage()),
          GoRoute(path: '/history', builder: (_, __) => const HistoryPage()),
          GoRoute(path: '/settings', builder: (_, __) => const SettingsPage()),
        ],
      ),
    ],
  );
});

class RenameifyShell extends ConsumerStatefulWidget {
  const RenameifyShell({
    required this.location,
    required this.child,
    super.key,
  });

  final String location;
  final Widget child;

  @override
  ConsumerState<RenameifyShell> createState() => _RenameifyShellState();
}

class _RenameifyShellState extends ConsumerState<RenameifyShell> {
  bool _loaded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_loaded) {
      return;
    }
    _loaded = true;
    Future.microtask(() {
      ref.read(appControllerProvider.notifier).loadConfig();
      ref.read(appControllerProvider.notifier).loadHistory();
    });
  }

  @override
  Widget build(BuildContext context) {
    final appState = ref.watch(appControllerProvider);
    final controller = ref.read(appControllerProvider.notifier);
    final colors = context.colors;

    return Scaffold(
      body: Container(
        color: colors.black,
        child: Row(
          children: [
            _Sidebar(location: widget.location),
            Expanded(
              child: Column(
                children: [
                  _TopBar(appState: appState, onCancel: controller.cancel),
                  Expanded(child: widget.child),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.location});

  final String location;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Container(
      width: 232,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colors.surface,
        border: Border(right: BorderSide(color: colors.line)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: colors.gold.withAlpha(22),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: colors.gold.withAlpha(110)),
                  boxShadow: [
                    BoxShadow(
                      color: colors.gold.withAlpha(38),
                      blurRadius: 20,
                      spreadRadius: -8,
                    ),
                  ],
                ),
                child: Icon(
                  LucideIcons.wandSparkles,
                  color: colors.teal,
                ),
              ),
              const SizedBox(width: 10),
              Text(
                'Renameify',
                style: TextStyle(
                  color: colors.text,
                  fontSize: 19,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ).animate().fadeIn(duration: 250.ms).slideX(begin: -0.04),
          const SizedBox(height: 28),
          _NavItem(
            icon: LucideIcons.folderSearch,
            label: 'Scan',
            path: '/scan',
            selected: location == '/scan',
          ),
          _NavItem(
            icon: LucideIcons.listChecks,
            label: 'Review',
            path: '/review',
            selected: location == '/review',
          ),
          _NavItem(
            icon: LucideIcons.history,
            label: 'History',
            path: '/history',
            selected: location == '/history',
          ),
          _NavItem(
            icon: LucideIcons.settings,
            label: 'Settings',
            path: '/settings',
            selected: location == '/settings',
          ),
          const Spacer(),
          const _ModeBadge(),
        ],
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.icon,
    required this.label,
    required this.path,
    required this.selected,
  });

  final IconData icon;
  final String label;
  final String path;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: () => context.go(path),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
          decoration: BoxDecoration(
            color: selected ? colors.teal.withAlpha(20) : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color:
                  selected ? colors.teal.withAlpha(120) : Colors.transparent,
            ),
            boxShadow:
                selected
                    ? [
                      BoxShadow(
                        color: colors.gold.withAlpha(24),
                        blurRadius: 16,
                        spreadRadius: -10,
                      ),
                    ]
                    : null,
          ),
          child: Row(
            children: [
              Icon(
                icon,
                size: 18,
                color: selected ? colors.teal : colors.muted,
              ),
              const SizedBox(width: 10),
              Text(
                label,
                style: TextStyle(
                  color: selected ? colors.tealSoft : colors.muted,
                  fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ModeBadge extends ConsumerWidget {
  const _ModeBadge();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final config = ref.watch(appControllerProvider).config;
    final colors = context.colors;
    final mode = config['mode'] as String? ?? 'media';
    final provider = config['llm_provider'] as String? ?? 'openai';
    final platform = config['platform'] as String? ?? 'generic';
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colors.panelAlt,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colors.line),
        boxShadow: [
          BoxShadow(
            color: colors.gold.withAlpha(14),
            blurRadius: 18,
            spreadRadius: -10,
          ),
        ],
      ),
      child: Row(
        children: [
          Icon(LucideIcons.monitorCog, color: colors.amber, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${mode.toUpperCase()} / $platform / $provider',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: colors.muted, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({required this.appState, required this.onCancel});

  final RenameifyState appState;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Container(
      height: 76,
      padding: const EdgeInsets.symmetric(horizontal: 22),
      decoration: BoxDecoration(
        color: colors.surface,
        border: Border(bottom: BorderSide(color: colors.line)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  appState.status,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 4),
                Text(
                  appState.detail,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          SizedBox(
            width: 210,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                minHeight: 8,
                value: appState.busy ? null : appState.progress.clamp(0, 1),
                backgroundColor: colors.panelAlt,
                color: colors.teal,
              ),
            ),
          ),
          const SizedBox(width: 14),
          OutlinedButton.icon(
            onPressed: appState.busy ? onCancel : null,
            icon: const Icon(LucideIcons.x, size: 16),
            label: const Text('Stop'),
          ),
        ],
      ),
    );
  }
}
