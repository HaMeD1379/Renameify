import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'app_controller.dart';
import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

class ScanPage extends ConsumerWidget {
  const ScanPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appState = ref.watch(appControllerProvider);
    final controller = ref.read(appControllerProvider.notifier);
    final colors = context.colors;
    final pathController = TextEditingController(text: appState.selectedPath);
    final config = appState.config;
    final recent =
        (config['recent_paths'] as List? ?? const []).map((e) => '$e').toList();

    return PageFrame(
      title: 'Scan & Rename',
      icon: LucideIcons.scanLine,
      child: Column(
        children: [
          Panel(
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: pathController,
                        onSubmitted: controller.setPath,
                        decoration: InputDecoration(
                          prefixIcon: const Icon(LucideIcons.folder, size: 18),
                          hintText: 'Media folder path',
                          suffixIcon:
                              recent.isEmpty
                                  ? null
                                  : PopupMenuButton<String>(
                                    tooltip: 'Recent folders',
                                    icon: const Icon(LucideIcons.history),
                                    onSelected: controller.setPath,
                                    itemBuilder:
                                        (_) => [
                                          for (final path in recent)
                                            PopupMenuItem(
                                              value: path,
                                              child: Text(path),
                                            ),
                                        ],
                                  ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    OutlinedButton.icon(
                      onPressed:
                          appState.busy
                              ? null
                              : () async {
                                final path =
                                    await FilePicker.getDirectoryPath();
                                if (path != null) {
                                  controller.setPath(path);
                                }
                              },
                      icon: const Icon(LucideIcons.folderOpen, size: 16),
                      label: const Text('Browse'),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    FilterChip(
                      selected: config['smart_folder_filter'] as bool? ?? true,
                      onSelected:
                          appState.busy
                              ? null
                              : (v) => controller.setConfigFlag(
                                'smart_folder_filter',
                                v,
                              ),
                      avatar: const Icon(LucideIcons.listFilter, size: 16),
                      label: const Text('Smart folder filter'),
                    ),
                    FilterChip(
                      selected: appState.includeLowConfidence,
                      onSelected: controller.setIncludeLowConfidence,
                      avatar: const Icon(LucideIcons.triangleAlert, size: 16),
                      label: const Text('Include low confidence'),
                    ),
                    FilterChip(
                      selected: appState.renameFolders,
                      onSelected:
                          appState.busy ? null : controller.setRenameFolders,
                      avatar: const Icon(LucideIcons.folderCog, size: 16),
                      label: const Text('Rename folders'),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    FilledButton.icon(
                      onPressed: appState.busy ? null : controller.scan,
                      icon: const Icon(LucideIcons.search, size: 16),
                      label: const Text('Discover Files'),
                    ),
                    const SizedBox(width: 10),
                    FilledButton.icon(
                      onPressed:
                          appState.busy
                              ? null
                              : () async {
                                await controller.identifyPlan();
                                if (context.mounted) {
                                  context.go('/review');
                                }
                              },
                      icon: const Icon(LucideIcons.sparkles, size: 16),
                      label: const Text('Identify & Plan'),
                    ),
                    const SizedBox(width: 10),
                    OutlinedButton.icon(
                      onPressed: appState.busy ? null : controller.clearResults,
                      icon: const Icon(LucideIcons.trash2, size: 16),
                      label: const Text('Clear'),
                    ),
                    const Spacer(),
                    Metric(
                      label: 'Files',
                      value: '${appState.mediaFiles.length}',
                    ),
                    const SizedBox(width: 10),
                    Metric(
                      label: 'Selected',
                      value: '${appState.selectedCount}',
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          Expanded(
            child: Panel(
              child:
                  appState.mediaFiles.isEmpty
                      ? const EmptyState(
                        icon: LucideIcons.folderSearch,
                        title: 'No files loaded',
                        detail:
                            'Discover files or run identify to build a plan.',
                      )
                      : ListView.separated(
                        itemCount: appState.mediaFiles.length,
                        separatorBuilder:
                            (_, __) => Divider(color: colors.line),
                        itemBuilder: (context, index) {
                          final file = appState.mediaFiles[index];
                          return ListTile(
                            dense: true,
                            leading: Icon(
                              LucideIcons.film,
                              color: colors.teal,
                            ),
                            title: Text(file.filename + file.extension),
                            subtitle: Text(
                              file.path,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            trailing: Wrap(
                              spacing: 10,
                              crossAxisAlignment: WrapCrossAlignment.center,
                              children: [
                                if (file.subtitles.isNotEmpty)
                                  Chip(
                                    visualDensity: VisualDensity.compact,
                                    label: Text(
                                      '${file.subtitles.length} subs',
                                    ),
                                  ),
                                Text('${file.sizeMb.toStringAsFixed(1)} MB'),
                              ],
                            ),
                          );
                        },
                      ),
            ),
          ),
        ],
      ),
    );
  }
}

class ReviewPage extends ConsumerWidget {
  const ReviewPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appState = ref.watch(appControllerProvider);
    final controller = ref.read(appControllerProvider.notifier);
    final rows = appState.plan?.rows ?? const <PlanRowModel>[];

    return PageFrame(
      title: 'Review Changes',
      icon: LucideIcons.listChecks,
      actions: [
        OutlinedButton(
          onPressed: rows.isEmpty ? null : () => controller.selectAllRows(true),
          child: const Text('Select All'),
        ),
        OutlinedButton(
          onPressed: rows.isEmpty ? null : controller.selectHighConfidenceOnly,
          child: const Text('High Only'),
        ),
        OutlinedButton(
          onPressed:
              rows.isEmpty ? null : () => controller.selectAllRows(false),
          child: const Text('Clear'),
        ),
        FilledButton.icon(
          onPressed:
              appState.busy || rows.isEmpty
                  ? null
                  : () async {
                    final ok = await _confirm(
                      context,
                      'Apply selected renames?',
                      '${appState.selectedCount} selected operation(s) will be applied.',
                    );
                    if (ok) {
                      await controller.applySelected();
                    }
                  },
          icon: const Icon(LucideIcons.check, size: 16),
          label: const Text('Apply Selected'),
        ),
      ],
      child: Panel(
        padding: EdgeInsets.zero,
        child:
            rows.isEmpty
                ? const EmptyState(
                  icon: LucideIcons.listChecks,
                  title: 'No plan ready',
                )
                : Scrollbar(
                  thumbVisibility: true,
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: SingleChildScrollView(
                      child: DataTable(
                        showCheckboxColumn: false,
                        columns: const [
                          DataColumn(label: Text('')),
                          DataColumn(label: Text('Type')),
                          DataColumn(label: Text('Original')),
                          DataColumn(label: Text('New')),
                          DataColumn(label: Text('Confidence')),
                          DataColumn(label: Text('Notes')),
                          DataColumn(label: Text('')),
                        ],
                        rows: [
                          for (final row in rows)
                            DataRow(
                              selected: _isRowSelected(appState, row),
                              cells: [
                                DataCell(
                                  Checkbox(
                                    value: _isRowSelected(appState, row),
                                    onChanged:
                                        row.bucket == 'Unknown'
                                            ? null
                                            : (value) => controller.toggleRow(
                                              row,
                                              value ?? false,
                                            ),
                                  ),
                                ),
                                DataCell(Bucket(bucket: row.bucket)),
                                DataCell(
                                  TableText(row.originalName, width: 250),
                                ),
                                DataCell(TableText(row.newName, width: 320)),
                                DataCell(Text('${row.confidence}%')),
                                DataCell(
                                  TableText(row.notes ?? '', width: 230),
                                ),
                                DataCell(
                                  Wrap(
                                    spacing: 4,
                                    children: [
                                      IconButton(
                                        tooltip: 'Edit new name',
                                        onPressed:
                                            () => _editName(
                                              context,
                                              controller,
                                              row,
                                            ),
                                        icon: const Icon(
                                          LucideIcons.pencil,
                                          size: 16,
                                        ),
                                      ),
                                      if (!row.isFolderRename)
                                        IconButton(
                                          tooltip: 'View/edit metadata',
                                          onPressed:
                                              () => _showMetadata(
                                                context,
                                                ref,
                                                row.originalPath,
                                              ),
                                          icon: const Icon(
                                            LucideIcons.badgeInfo,
                                            size: 16,
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
      ),
    );
  }

  bool _isRowSelected(RenameifyState state, PlanRowModel row) {
    if (row.isFolderRename) {
      final index = row.folderRenameIndex;
      return index != null && state.selectedFolderRenameIndexes.contains(index);
    }
    return state.selectedOperationPaths.contains(row.originalPath);
  }
}

class HistoryPage extends ConsumerWidget {
  const HistoryPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appState = ref.watch(appControllerProvider);
    final controller = ref.read(appControllerProvider.notifier);
    final colors = context.colors;

    return PageFrame(
      title: 'History',
      icon: LucideIcons.history,
      actions: [
        OutlinedButton.icon(
          onPressed: controller.loadHistory,
          icon: const Icon(LucideIcons.refreshCw, size: 16),
          label: const Text('Refresh'),
        ),
      ],
      child: Panel(
        child:
            appState.history.isEmpty
                ? const EmptyState(
                  icon: LucideIcons.history,
                  title: 'No manifests',
                )
                : ListView.separated(
                  itemCount: appState.history.length,
                  separatorBuilder:
                      (_, __) => Divider(color: colors.line),
                  itemBuilder: (context, index) {
                    final item = appState.history[index];
                    final id = item['id'] as String? ?? '';
                    final applied = item['applied'] == true;
                    final rolledBack = item['rolled_back'] == true;
                    final ops =
                        item['total_operations'] ??
                        (item['operations'] as List? ?? const []).length;
                    return ListTile(
                      leading: Icon(
                        rolledBack ? LucideIcons.undo : LucideIcons.database,
                        color: rolledBack ? colors.muted : colors.teal,
                      ),
                      title: Text(id),
                      subtitle: Text(
                        '${item['timestamp'] ?? ''}\n${item['root_path'] ?? ''}',
                      ),
                      isThreeLine: true,
                      trailing: Wrap(
                        spacing: 10,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          Chip(label: Text('$ops ops')),
                          OutlinedButton.icon(
                            onPressed:
                                applied && !rolledBack
                                    ? () async {
                                      final ok = await _confirm(
                                        context,
                                        'Rollback this operation?',
                                        id,
                                      );
                                      if (ok) {
                                        await controller.rollback(id);
                                      }
                                    }
                                    : null,
                            icon: const Icon(LucideIcons.rotateCcw, size: 16),
                            label: const Text('Rollback'),
                          ),
                        ],
                      ),
                    );
                  },
                ),
      ),
    );
  }
}

class _PlexOption {
  const _PlexOption(this.value, this.label, this.detail);

  final String value;
  final String label;
  final String detail;
}

const _plexAgentOptions = [
  _PlexOption('auto', 'Auto', 'Use normal Renameify detection.'),
  _PlexOption('plex_movie', 'Plex Movie', 'Current movie metadata agent.'),
  _PlexOption('plex_series', 'Plex Series', 'Current TV metadata agent.'),
  _PlexOption(
    'personal_media',
    'Personal Media',
    'No online matching for ambiguous files.',
  ),
  _PlexOption('legacy_thetvdb', 'TheTVDB (Legacy)', 'Older TV metadata agent.'),
  _PlexOption('legacy_tmdb', 'TMDB (Legacy)', 'Older movie metadata agent.'),
];

const _plexScannerOptions = [
  _PlexOption('auto', 'Auto', 'Classify movies and shows from context.'),
  _PlexOption('plex_movie', 'Plex Movie', 'Current movie scanner.'),
  _PlexOption('plex_tv_series', 'Plex TV Series', 'Current TV scanner.'),
  _PlexOption(
    'plex_video_files',
    'Plex Video Files',
    'Personal video scanner.',
  ),
  _PlexOption(
    'legacy_movie',
    'Plex Movie Scanner (Legacy)',
    'Older movie scanner.',
  ),
  _PlexOption(
    'legacy_series',
    'Plex Series Scanner (Legacy)',
    'Older TV scanner.',
  ),
];

const _plexOrderingOptions = [
  _PlexOption('tmdb_aired', 'TMDB (Aired)', 'Default Plex Series ordering.'),
  _PlexOption('tvdb_aired', 'TheTVDB (Aired)', 'TVDB aired order.'),
  _PlexOption('tvdb_dvd', 'TheTVDB (DVD)', 'DVD/Blu-ray order.'),
  _PlexOption(
    'tvdb_absolute',
    'TheTVDB (Absolute)',
    'Absolute/anime-style order.',
  ),
];

class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  final _apiKey = TextEditingController();
  final _model = TextEditingController();
  final _customPrompt = TextEditingController();
  String _provider = 'openai';
  String _platform = 'generic';
  String _mode = 'media';

  @override
  void dispose() {
    _apiKey.dispose();
    _model.dispose();
    _customPrompt.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final appState = ref.watch(appControllerProvider);
    final controller = ref.read(appControllerProvider.notifier);
    final config = appState.config;
    final colors = context.colors;
    _provider = config['llm_provider'] as String? ?? _provider;
    _platform = config['platform'] as String? ?? _platform;
    _mode = config['mode'] as String? ?? _mode;
    final plexAgent = _optionValue(
      config['plex_agent'] as String?,
      _plexAgentOptions,
    );
    final plexScanner = _optionValue(
      config['plex_scanner'] as String?,
      _plexScannerOptions,
    );
    final plexOrdering = _optionValue(
      config['plex_episode_ordering'] as String?,
      _plexOrderingOptions,
    );
    _apiKey.text = config['${_provider}_api_key'] as String? ?? '';
    _model.text = config['${_provider}_model'] as String? ?? '';
    _customPrompt.text = config['custom_prompt'] as String? ?? '';

    return PageFrame(
      title: 'Settings',
      icon: LucideIcons.settings,
      child: SingleChildScrollView(
        child: Column(
          children: [
            Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionTitle(
                    'Naming Mode',
                    icon: LucideIcons.layoutDashboard,
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: SegmentedButton<String>(
                          segments: const [
                            ButtonSegment(
                              value: 'media',
                              label: Text('Media'),
                              icon: Icon(LucideIcons.film),
                            ),
                            ButtonSegment(
                              value: 'mass',
                              label: Text('Mass Rename'),
                              icon: Icon(LucideIcons.files),
                            ),
                          ],
                          selected: {_mode},
                          onSelectionChanged:
                              (v) => controller.saveSettings({'mode': v.first}),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          initialValue: _platform,
                          decoration: const InputDecoration(
                            labelText: 'Platform',
                          ),
                          dropdownColor: colors.panel,
                          items: const [
                            DropdownMenuItem(
                              value: 'generic',
                              child: Text('Generic'),
                            ),
                            DropdownMenuItem(
                              value: 'plex',
                              child: Text('Plex'),
                            ),
                            DropdownMenuItem(
                              value: 'jellyfin',
                              child: Text('Jellyfin'),
                            ),
                            DropdownMenuItem(
                              value: 'emby',
                              child: Text('Emby'),
                            ),
                          ],
                          onChanged:
                              (value) =>
                                  value == null
                                      ? null
                                      : controller.saveSettings({
                                        'platform': value,
                                      }),
                        ),
                      ),
                    ],
                  ),
                  if (_platform == 'plex') ...[
                    const SizedBox(height: 12),
                    const SectionTitle(
                      'Plex Library Options',
                      icon: LucideIcons.library,
                    ),
                    const SizedBox(height: 10),
                    SwitchListTile(
                      value: config['plex_options_enabled'] as bool? ?? false,
                      onChanged:
                          (v) => controller.saveSettings({
                            'plex_options_enabled': v,
                          }),
                      title: const Text('Use Plex scanner and agent rules'),
                      contentPadding: EdgeInsets.zero,
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: DropdownButtonFormField<String>(
                            initialValue: plexScanner,
                            decoration: const InputDecoration(
                              labelText: 'Scanner',
                              prefixIcon: Icon(
                                LucideIcons.scanSearch,
                                size: 18,
                              ),
                            ),
                            dropdownColor: colors.panel,
                            items:
                                _plexScannerOptions
                                    .map(
                                      (option) => DropdownMenuItem(
                                        value: option.value,
                                        child: _OptionLabel(option),
                                      ),
                                    )
                                    .toList(),
                            onChanged:
                                (value) =>
                                    value == null
                                        ? null
                                        : controller.saveSettings({
                                          'plex_options_enabled': true,
                                          'plex_scanner': value,
                                          if (value == 'plex_movie' ||
                                              value == 'legacy_movie')
                                            'plex_agent': 'plex_movie',
                                          if (value == 'plex_tv_series' ||
                                              value == 'legacy_series')
                                            'plex_agent': 'plex_series',
                                          if (value == 'plex_video_files')
                                            'plex_agent': 'personal_media',
                                        }),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: DropdownButtonFormField<String>(
                            initialValue: plexAgent,
                            decoration: const InputDecoration(
                              labelText: 'Agent',
                              prefixIcon: Icon(LucideIcons.bot, size: 18),
                            ),
                            dropdownColor: colors.panel,
                            items:
                                _plexAgentOptions
                                    .map(
                                      (option) => DropdownMenuItem(
                                        value: option.value,
                                        child: _OptionLabel(option),
                                      ),
                                    )
                                    .toList(),
                            onChanged:
                                (value) =>
                                    value == null
                                        ? null
                                        : controller.saveSettings({
                                          'plex_options_enabled': true,
                                          'plex_agent': value,
                                        }),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: DropdownButtonFormField<String>(
                            initialValue: plexOrdering,
                            decoration: const InputDecoration(
                              labelText: 'Episode Ordering',
                              prefixIcon: Icon(
                                LucideIcons.listOrdered,
                                size: 18,
                              ),
                            ),
                            dropdownColor: colors.panel,
                            items:
                                _plexOrderingOptions
                                    .map(
                                      (option) => DropdownMenuItem(
                                        value: option.value,
                                        child: _OptionLabel(option),
                                      ),
                                    )
                                    .toList(),
                            onChanged:
                                plexScanner == 'plex_tv_series' ||
                                        plexScanner == 'legacy_series'
                                    ? (value) =>
                                        value == null
                                            ? null
                                            : controller.saveSettings({
                                              'plex_options_enabled': true,
                                              'plex_episode_ordering': value,
                                            })
                                    : null,
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 14),
            Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionTitle('LLM Provider', icon: LucideIcons.bot),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          initialValue: _provider,
                          decoration: const InputDecoration(
                            labelText: 'Provider',
                          ),
                          dropdownColor: colors.panel,
                          items: const [
                            DropdownMenuItem(
                              value: 'openai',
                              child: Text('OpenAI'),
                            ),
                            DropdownMenuItem(
                              value: 'anthropic',
                              child: Text('Anthropic'),
                            ),
                            DropdownMenuItem(
                              value: 'google',
                              child: Text('Google'),
                            ),
                            DropdownMenuItem(
                              value: 'openrouter',
                              child: Text('OpenRouter'),
                            ),
                          ],
                          onChanged:
                              (value) =>
                                  value == null
                                      ? null
                                      : controller.saveSettings({
                                        'llm_provider': value,
                                      }),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextField(
                          controller: _apiKey,
                          obscureText: true,
                          decoration: const InputDecoration(
                            labelText: 'API Key',
                            prefixIcon: Icon(LucideIcons.key, size: 18),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _model,
                          decoration: InputDecoration(
                            labelText: 'Model',
                            prefixIcon: const Icon(
                              LucideIcons.server,
                              size: 18,
                            ),
                            suffixIcon: PopupMenuButton<String>(
                              tooltip: 'Top web-search models',
                              icon: const Icon(LucideIcons.chevronsUpDown),
                              onSelected: (value) => _model.text = value,
                              itemBuilder:
                                  (_) => [
                                    for (final model in appState.models)
                                      PopupMenuItem(
                                        value: model.id,
                                        child: _ModelOptionLabel(model),
                                      ),
                                  ],
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      FilledButton.icon(
                        onPressed:
                            () => controller.saveSettings({
                              'llm_provider': _provider,
                              '${_provider}_api_key': _apiKey.text,
                              '${_provider}_model': _model.text,
                            }),
                        icon: const Icon(LucideIcons.save, size: 16),
                        label: const Text('Save'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton.icon(
                        onPressed:
                            appState.busy
                                ? null
                                : () => controller.testAndRefreshModels(
                                  provider: _provider,
                                  apiKey: _apiKey.text.trim(),
                                  model: _model.text.trim(),
                                ),
                        icon: const Icon(LucideIcons.refreshCw, size: 16),
                        label: const Text('Test Web & Refresh'),
                      ),
                    ],
                  ),
                  if (appState.models.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    _ModelOptionStrip(
                      models: appState.models,
                      selectedModel: _model.text,
                      onSelected:
                          (value) => setState(() {
                            _model.text = value;
                          }),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 14),
            Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionTitle(
                    'General',
                    icon: LucideIcons.slidersHorizontal,
                  ),
                  const SizedBox(height: 8),
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(
                        value: 'dark',
                        label: Text('Dark'),
                        icon: Icon(LucideIcons.moon),
                      ),
                      ButtonSegment(
                        value: 'light',
                        label: Text('Light'),
                        icon: Icon(LucideIcons.sun),
                      ),
                      ButtonSegment(
                        value: 'system',
                        label: Text('System'),
                        icon: Icon(LucideIcons.monitor),
                      ),
                    ],
                    selected: {
                      switch ('${config['ui_theme'] ?? 'dark'}'.toLowerCase()) {
                        'light' => 'light',
                        'system' => 'system',
                        _ => 'dark',
                      },
                    },
                    onSelectionChanged:
                        (v) => controller.saveSettings({'ui_theme': v.first}),
                  ),
                  const SizedBox(height: 8),
                  SwitchListTile(
                    value: config['restructure_folders'] as bool? ?? true,
                    onChanged:
                        (v) =>
                            controller.saveSettings({'restructure_folders': v}),
                    title: const Text('Restructure folders'),
                    contentPadding: EdgeInsets.zero,
                  ),
                  SwitchListTile(
                    value: config['rename_subtitles'] as bool? ?? true,
                    onChanged:
                        (v) => controller.saveSettings({'rename_subtitles': v}),
                    title: const Text('Rename subtitles alongside video files'),
                    contentPadding: EdgeInsets.zero,
                  ),
                  SwitchListTile(
                    value: config['use_web_search'] as bool? ?? true,
                    onChanged:
                        (v) => controller.saveSettings({'use_web_search': v}),
                    title: const Text(
                      'Use web search when the provider supports it',
                    ),
                    contentPadding: EdgeInsets.zero,
                  ),
                  Row(
                    children: [
                      Expanded(
                        child: _NumberField(
                          label: 'Confidence Threshold',
                          value: config['confidence_threshold'] as int? ?? 80,
                          min: 0,
                          max: 100,
                          onChanged:
                              (v) => controller.saveSettings({
                                'confidence_threshold': v,
                              }),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _NumberField(
                          label: 'Batch Size',
                          value: config['gpt_batch_size'] as int? ?? 12,
                          min: 1,
                          max: 50,
                          onChanged:
                              (v) => controller.saveSettings({
                                'gpt_batch_size': v,
                              }),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionTitle(
                    'Custom Prompt',
                    icon: LucideIcons.messageSquareText,
                  ),
                  const SizedBox(height: 8),
                  SwitchListTile(
                    value: config['custom_prompt_enabled'] as bool? ?? false,
                    onChanged:
                        (v) => controller.saveSettings({
                          'custom_prompt_enabled': v,
                        }),
                    title: const Text('Enable custom prompt override'),
                    contentPadding: EdgeInsets.zero,
                  ),
                  TextField(
                    controller: _customPrompt,
                    minLines: 4,
                    maxLines: 8,
                    decoration: const InputDecoration(
                      hintText:
                          'Describe the naming pattern or identification rules to use.',
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      FilledButton.icon(
                        onPressed:
                            () => controller.saveSettings({
                              'custom_prompt': _customPrompt.text,
                              'custom_prompt_enabled':
                                  _customPrompt.text.trim().isNotEmpty,
                            }),
                        icon: const Icon(LucideIcons.save, size: 16),
                        label: const Text('Save Prompt'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton.icon(
                        onPressed:
                            () => controller.saveSettings({
                              'custom_prompt': '',
                              'custom_prompt_enabled': false,
                            }),
                        icon: const Icon(LucideIcons.x, size: 16),
                        label: const Text('Clear'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            Panel(
              child: Row(
                children: [
                  Icon(LucideIcons.folderCog, color: colors.amber),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      appState.configDir.isEmpty
                          ? 'Config folder unavailable'
                          : appState.configDir,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: controller.openConfigFolder,
                    icon: const Icon(LucideIcons.externalLink, size: 16),
                    label: const Text('Open Config Folder'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _optionValue(String? value, List<_PlexOption> options) {
  if (value != null && options.any((option) => option.value == value)) {
    return value;
  }
  return options.first.value;
}

class _OptionLabel extends StatelessWidget {
  const _OptionLabel(this.option);

  final _PlexOption option;

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 260),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(option.label, overflow: TextOverflow.ellipsis),
          Text(
            option.detail,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _ModelOptionLabel extends StatelessWidget {
  const _ModelOptionLabel(this.model);

  final ModelOption model;

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 360),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  model.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (model.costTier.isNotEmpty) ...[
                const SizedBox(width: 8),
                Text(
                  model.costTier,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ],
            ],
          ),
          Text(
            model.id,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
  }
}

class _ModelOptionStrip extends StatelessWidget {
  const _ModelOptionStrip({
    required this.models,
    required this.selectedModel,
    required this.onSelected,
  });

  final List<ModelOption> models;
  final String selectedModel;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final model in models.take(5))
          _ModelOptionTile(
            model: model,
            selected: model.id == selectedModel,
            onTap: () => onSelected(model.id),
          ),
      ],
    );
  }
}

class _ModelOptionTile extends StatelessWidget {
  const _ModelOptionTile({
    required this.model,
    required this.selected,
    required this.onTap,
  });

  final ModelOption model;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final color = selected ? colors.gold : colors.line;
    return InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 140),
        width: 196,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color:
              selected
                  ? colors.gold.withAlpha(24)
                  : colors.panelAlt,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    model.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                if (model.costTier.isNotEmpty)
                  Text(
                    model.costTier,
                    style: TextStyle(
                      color: selected ? colors.goldSoft : colors.muted,
                      fontWeight: FontWeight.w800,
                      fontSize: 11,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              model.id,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontSize: 10,
              ),
            ),
            if (model.detail.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                model.detail,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _NumberField extends StatelessWidget {
  const _NumberField({
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
  });

  final String label;
  final int value;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: Text(label)),
        IconButton(
          onPressed: value <= min ? null : () => onChanged(value - 1),
          icon: const Icon(LucideIcons.minus, size: 16),
        ),
        SizedBox(width: 44, child: Center(child: Text('$value'))),
        IconButton(
          onPressed: value >= max ? null : () => onChanged(value + 1),
          icon: const Icon(LucideIcons.plus, size: 16),
        ),
      ],
    );
  }
}

Future<bool> _confirm(BuildContext context, String title, String detail) async {
  return await showDialog<bool>(
        context: context,
        builder:
            (context) => AlertDialog(
              title: Text(title),
              content: Text(detail),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('Continue'),
                ),
              ],
            ),
      ) ??
      false;
}

Future<void> _editName(
  BuildContext context,
  AppController controller,
  PlanRowModel row,
) async {
  final text = TextEditingController(text: row.newName);
  final result = await showDialog<String>(
    context: context,
    builder:
        (context) => AlertDialog(
          title: const Text('Edit New Name'),
          content: TextField(controller: text, autofocus: true),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, text.text),
              child: const Text('Save'),
            ),
          ],
        ),
  );
  if (result != null && result.trim().isNotEmpty) {
    await controller.editRow(row, result);
  }
}

Future<void> _showMetadata(
  BuildContext context,
  WidgetRef ref,
  String path,
) async {
  final controller = ref.read(appControllerProvider.notifier);
  await controller.readMetadata(path);
  if (!context.mounted) {
    return;
  }
  await showDialog<void>(
    context: context,
    builder: (_) => _MetadataDialog(path: path),
  );
}

class _MetadataDialog extends ConsumerStatefulWidget {
  const _MetadataDialog({required this.path});

  final String path;

  @override
  ConsumerState<_MetadataDialog> createState() => _MetadataDialogState();
}

class _MetadataDialogState extends ConsumerState<_MetadataDialog> {
  final _controllers = <String, TextEditingController>{};

  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final metadata = ref.watch(appControllerProvider).metadata;
    if (metadata == null) {
      return const AlertDialog(
        content: SizedBox(
          height: 120,
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }
    for (final entry in metadata.values.entries) {
      _controllers.putIfAbsent(
        entry.key,
        () => TextEditingController(text: entry.value?.toString() ?? ''),
      );
    }

    return AlertDialog(
      title: Text('Metadata - ${basename(widget.path)}'),
      content: SizedBox(
        width: 620,
        child:
            !metadata.isReadable
                ? Text(metadata.error ?? 'File metadata could not be read.')
                : SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (final field in metadata.values.keys)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: TextField(
                            controller: _controllers[field],
                            decoration: InputDecoration(
                              labelText: field.replaceAll('_', ' '),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        FilledButton(
          onPressed:
              metadata.isReadable
                  ? () async {
                    final updates = {
                      for (final entry in _controllers.entries)
                        entry.key:
                            entry.value.text.trim().isEmpty
                                ? null
                                : entry.value.text.trim(),
                    };
                    await ref
                        .read(appControllerProvider.notifier)
                        .writeMetadata(widget.path, updates);
                    if (context.mounted) {
                      Navigator.pop(context);
                    }
                  }
                  : null,
          child: const Text('Save Changes'),
        ),
      ],
    );
  }
}
