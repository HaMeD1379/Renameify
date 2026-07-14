import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'bridge_client.dart';
import 'models.dart';

final appControllerProvider = NotifierProvider<AppController, RenameifyState>(
  AppController.new,
);

class AppController extends Notifier<RenameifyState> {
  late final BridgeClient _bridge;
  StreamSubscription<BridgeEvent>? _subscription;

  @override
  RenameifyState build() {
    _bridge = ref.watch(bridgeClientProvider);
    _subscription = _bridge.events.listen(_handleBridgeEvent);
    ref.onDispose(() => _subscription?.cancel());
    return RenameifyState.initial();
  }

  Future<void> loadConfig() async {
    try {
      final event = await _bridge.send('config.load', {});
      final config =
          (event.data['config'] as Map?)?.cast<String, dynamic>() ?? {};
      state = state.copyWith(
        config: config,
        selectedPath: config['last_path'] as String? ?? state.selectedPath,
        detail:
            (config['last_path'] as String?)?.isNotEmpty == true
                ? config['last_path'] as String
                : state.detail,
        renameFolders: config['rename_folders'] as bool? ?? true,
      );
      await loadModels();
      await loadConfigInfo();
    } catch (error) {
      _fail(error);
    }
  }

  void setPath(String path) {
    state = state.copyWith(
      selectedPath: path,
      detail: path.isEmpty ? 'Select a media folder to begin.' : path,
      clearPlan: true,
      mediaFiles: [],
      selectedOperationPaths: {},
      selectedFolderRenameIndexes: {},
    );
  }

  Future<void> clearResults() async {
    state = state.copyWith(
      status: 'Ready',
      detail:
          state.selectedPath.isEmpty
              ? 'Select a media folder to begin.'
              : state.selectedPath,
      progress: 0,
      mediaFiles: [],
      clearPlan: true,
      selectedOperationPaths: {},
      selectedFolderRenameIndexes: {},
      clearMetadata: true,
    );
  }

  Future<void> scan() async {
    if (state.selectedPath.isEmpty) {
      state = state.copyWith(
        status: 'Select a folder',
        detail: 'No path selected.',
      );
      return;
    }

    await _busy('Scanning', () async {
      final event = await _bridge.send('scan', {
        'path': state.selectedPath,
        'config': state.config,
      });
      final files =
          (event.data['media_files'] as List? ?? const [])
              .map(
                (item) => MediaFileModel.fromJson(
                  (item as Map).cast<String, dynamic>(),
                ),
              )
              .toList();
      state = state.copyWith(
        config: {
          ...state.config,
          'last_path': state.selectedPath,
          'recent_paths':
              event.data['recent_paths'] ?? state.config['recent_paths'] ?? [],
        },
        mediaFiles: files,
        progress: 1,
        status: 'Scan complete',
        detail: '${files.length} media files found.',
        clearPlan: true,
        selectedOperationPaths: {},
        selectedFolderRenameIndexes: {},
      );
    });
  }

  Future<void> identifyPlan() async {
    if (state.selectedPath.isEmpty) {
      state = state.copyWith(
        status: 'Select a folder',
        detail: 'No path selected.',
      );
      return;
    }

    await _busy('Identifying', () async {
      final event = await _bridge.send('identify_plan', {
        'path': state.selectedPath,
        'config': state.config,
        'media_files': state.mediaFiles.map((item) => item.toJson()).toList(),
        'custom_prompt':
            state.config['custom_prompt_enabled'] == true
                ? state.config['custom_prompt']
                : null,
      });
      final plan = PlanModel.fromJson(
        (event.data['plan'] as Map).cast<String, dynamic>(),
      );
      state = state.copyWith(
        plan: plan,
        progress: 1,
        status: 'Plan ready',
        detail:
            '${plan.highConfidence.length + plan.lowConfidence.length} file renames, ${plan.folderRenames.length} folder renames.',
        selectedOperationPaths: {
          for (final row in plan.rows)
            if (!row.isFolderRename &&
                row.bucket != 'Unknown' &&
                (row.bucket == 'High' || state.includeLowConfidence))
              row.originalPath,
        },
        selectedFolderRenameIndexes: {
          for (final row in plan.rows)
            if (row.isFolderRename && row.folderRenameIndex != null)
              row.folderRenameIndex!,
        },
      );
    });
  }

  void toggleRow(PlanRowModel row, bool selected) {
    if (row.isFolderRename) {
      final next = {...state.selectedFolderRenameIndexes};
      final index = row.folderRenameIndex;
      if (index != null) {
        selected ? next.add(index) : next.remove(index);
      }
      state = state.copyWith(selectedFolderRenameIndexes: next);
      return;
    }

    final next = {...state.selectedOperationPaths};
    selected ? next.add(row.originalPath) : next.remove(row.originalPath);
    state = state.copyWith(selectedOperationPaths: next);
  }

  void selectAllRows(bool selected) {
    final plan = state.plan;
    if (plan == null) {
      return;
    }
    state = state.copyWith(
      selectedOperationPaths:
          selected
              ? {
                for (final row in plan.rows)
                  if (!row.isFolderRename && row.bucket != 'Unknown')
                    row.originalPath,
              }
              : {},
      selectedFolderRenameIndexes:
          selected
              ? {
                for (final row in plan.rows)
                  if (row.isFolderRename && row.folderRenameIndex != null)
                    row.folderRenameIndex!,
              }
              : {},
    );
  }

  void selectHighConfidenceOnly() {
    final plan = state.plan;
    if (plan == null) {
      return;
    }
    state = state.copyWith(
      selectedOperationPaths: {
        for (final row in plan.rows)
          if (!row.isFolderRename && row.bucket == 'High') row.originalPath,
      },
      selectedFolderRenameIndexes: {},
    );
  }

  void setIncludeLowConfidence(bool value) {
    state = state.copyWith(includeLowConfidence: value);
  }

  Future<void> setRenameFolders(bool value) async {
    state = state.copyWith(renameFolders: value);
    await saveSettings({'rename_folders': value});
  }

  Future<void> setConfigFlag(String key, bool value) async {
    await saveSettings({key: value});
  }

  Future<void> editRow(PlanRowModel row, String newName) async {
    final plan = state.plan;
    if (plan == null || newName.trim().isEmpty) {
      return;
    }

    final nextPlan =
        row.isFolderRename && row.folderRenameIndex != null
            ? plan.withEditedFolderPath(row.folderRenameIndex!, newName)
            : plan.withEditedNewPath(row.originalPath, newName);
    state = state.copyWith(
      plan: nextPlan,
      status: 'Plan edited',
      detail: newName,
    );
  }

  Future<void> applySelected() async {
    final plan = state.plan;
    if (plan == null) {
      state = state.copyWith(
        status: 'No plan',
        detail: 'Run identification first.',
      );
      return;
    }
    if (state.selectedCount == 0) {
      state = state.copyWith(
        status: 'Nothing selected',
        detail: 'Select at least one row.',
      );
      return;
    }

    await _busy('Applying', () async {
      final event = await _bridge.send('apply_selected', {
        'plan_id': plan.manifest.id,
        'plan': {
          'manifest': {
            'id': plan.manifest.id,
            'timestamp': DateTime.now().toIso8601String(),
            'root_path': plan.manifest.rootPath,
            'operations': plan.manifest.operations,
            'folder_renames': plan.folderRenames,
            'applied': false,
            'rolled_back': false,
          },
          'high_confidence': plan.highConfidence,
          'low_confidence': plan.lowConfidence,
          'unknown': plan.unknown,
          'skipped': plan.skipped,
          'folder_renames': plan.folderRenames,
        },
        'selected_operation_paths': state.selectedOperationPaths.toList(),
        'selected_folder_rename_indexes':
            state.renameFolders
                ? state.selectedFolderRenameIndexes.toList()
                : <int>[],
        'include_low_confidence': state.includeLowConfidence,
        'include_folder_renames': state.renameFolders,
        'config': state.config,
      });
      state = state.copyWith(
        progress: 1,
        status: 'Apply complete',
        detail:
            '${event.data['success'] ?? 0} applied, ${event.data['failed'] ?? 0} failed.',
      );
      await loadHistory();
    });
  }

  Future<void> loadHistory() async {
    try {
      final event = await _bridge.send('history', {'config': state.config});
      state = state.copyWith(
        history:
            (event.data['manifests'] as List? ?? const [])
                .map((item) => (item as Map).cast<String, dynamic>())
                .toList(),
      );
    } catch (error) {
      _fail(error);
    }
  }

  Future<void> rollback(String manifestId) async {
    await _busy('Rolling back', () async {
      final event = await _bridge.send('rollback', {
        'manifest_id': manifestId,
        'config': state.config,
      });
      state = state.copyWith(
        progress: 1,
        status: 'Rollback complete',
        detail:
            '${event.data['success'] ?? 0} restored, ${event.data['failed'] ?? 0} failed.',
      );
      await loadHistory();
    });
  }

  Future<void> saveSettings(Map<String, dynamic> partial) async {
    try {
      final merged = {...state.config, ...partial};
      final event = await _bridge.send('config.save', {'config': merged});
      state = state.copyWith(
        config:
            (event.data['config'] as Map?)?.cast<String, dynamic>() ?? merged,
        renameFolders:
            ((event.data['config'] as Map?)?['rename_folders'] as bool?) ??
            state.renameFolders,
        status: 'Settings saved',
        detail: 'Configuration updated.',
      );
      await loadModels();
    } catch (error) {
      _fail(error);
    }
  }

  Future<void> testConnection() async {
    await _busy('Testing provider', () async {
      final provider = state.config['llm_provider'] as String? ?? 'openai';
      final config = {
        ...state.config,
        if (provider == 'openai') 'use_web_search': true,
      };
      final event = await _bridge.send('test_connection', {
        'provider': provider,
        'api_key': state.config['${provider}_api_key'] ?? '',
        'model': state.config['${provider}_model'],
        'config': config,
      });
      state = state.copyWith(
        progress: 1,
        status: 'Provider connected',
        detail:
            '${event.data['provider']} / ${event.data['model']}'
            '${event.data['web_search'] == true ? ' / web search' : ''}',
      );
    });
  }

  Future<void> loadModels() async {
    try {
      final provider = state.config['llm_provider'] as String? ?? 'openai';
      final event = await _bridge.send('models.list', {'provider': provider});
      state = state.copyWith(
        models:
            (event.data['models'] as List? ?? const [])
                .map(
                  (item) => ModelOption.fromJson(
                    (item as Map).cast<String, dynamic>(),
                  ),
                )
                .toList(),
      );
    } catch (error) {
      _fail(error);
    }
  }

  Future<void> testAndRefreshModels({
    String? provider,
    String? apiKey,
    String? model,
  }) async {
    await _busy('Testing web models', () async {
      final selectedProvider =
          provider ?? (state.config['llm_provider'] as String? ?? 'openai');
      final key =
          apiKey ?? (state.config['${selectedProvider}_api_key'] as String? ?? '');
      final selectedModel =
          model ?? (state.config['${selectedProvider}_model'] as String? ?? '');
      final testConfig = {
        ...state.config,
        'llm_provider': selectedProvider,
        '${selectedProvider}_api_key': key,
        if (selectedModel.trim().isNotEmpty)
          '${selectedProvider}_model': selectedModel.trim(),
        'use_web_search': true,
        'require_web_search': true,
      };
      final test = await _bridge.send('test_connection', {
        'provider': selectedProvider,
        'api_key': key,
        'model': selectedModel.trim().isEmpty ? null : selectedModel.trim(),
        'config': testConfig,
      });
      final models = await _bridge.send('models.fetch', {
        'provider': selectedProvider,
        'api_key': key,
      });
      final parsedModels =
          (models.data['models'] as List? ?? const [])
              .map(
                (item) => ModelOption.fromJson(
                  (item as Map).cast<String, dynamic>(),
                ),
              )
              .toList();
      final modelIds = {for (final item in parsedModels) item.id};
      final resolvedModel =
          '${test.data['model'] ?? ''}'.trim().isNotEmpty
              ? '${test.data['model']}'.trim()
              : selectedModel.trim();
      final savedModel =
          modelIds.contains(resolvedModel)
              ? resolvedModel
              : (parsedModels.isNotEmpty
                  ? parsedModels.first.id
                  : resolvedModel);
      final savedConfig = {
        ...state.config,
        'llm_provider': selectedProvider,
        '${selectedProvider}_api_key': key,
        if (savedModel.isNotEmpty) '${selectedProvider}_model': savedModel,
        'use_web_search': true,
      };
      final saved = await _bridge.send('config.save', {'config': savedConfig});
      state = state.copyWith(
        config:
            (saved.data['config'] as Map?)?.cast<String, dynamic>() ??
            savedConfig,
        progress: 1,
        status: 'Web search ready',
        detail:
            '${test.data['provider']} / $savedModel - ${parsedModels.length} web models',
        models: parsedModels,
      );
    });
  }

  Future<void> loadConfigInfo() async {
    try {
      final event = await _bridge.send('config.info', {});
      state = state.copyWith(
        configDir: event.data['config_dir'] as String? ?? '',
      );
    } catch (_) {
      // Non-critical.
    }
  }

  Future<void> openConfigFolder() async {
    try {
      await _bridge.send('config.open_dir', {});
    } catch (error) {
      _fail(error);
    }
  }

  Future<void> readMetadata(String path) async {
    await _busy('Reading metadata', () async {
      final event = await _bridge.send('metadata.read', {'path': path});
      state = state.copyWith(
        progress: 1,
        status: 'Metadata loaded',
        detail: path,
        metadata: FileMetadataModel.fromJson(
          (event.data['metadata'] as Map).cast<String, dynamic>(),
        ),
      );
    });
  }

  Future<void> writeMetadata(String path, Map<String, dynamic> updates) async {
    await _busy('Saving metadata', () async {
      final event = await _bridge.send('metadata.write', {
        'path': path,
        'updates': updates,
      });
      final ok = event.data['success'] == true;
      state = state.copyWith(
        progress: 1,
        status: ok ? 'Metadata saved' : 'Metadata unchanged',
        detail: path,
      );
      await readMetadata(path);
    });
  }

  Future<void> cancel() async {
    try {
      await _bridge.send('cancel', {});
      state = state.copyWith(
        busy: false,
        status: 'Cancelling',
        detail: 'Cancel request sent.',
      );
    } catch (error) {
      _fail(error);
    }
  }

  void _handleBridgeEvent(BridgeEvent event) {
    if (event.type != 'progress') {
      return;
    }

    if (event.command == 'scan') {
      final found = event.data['files_found'] ?? 0;
      final folders = event.data['folders_scanned'] ?? 0;
      final phase = event.data['phase'] as String? ?? 'scanning';
      state = state.copyWith(
        status: phase == 'filtering' ? 'Filtering folders' : 'Scanning',
        detail:
            event.data['current_folder'] as String? ??
            '$found files found across $folders folders.',
        progress: 0.12,
      );
    } else if (event.command == 'identify_plan') {
      final processed =
          (event.data['files_processed'] as num?)?.toDouble() ?? 0;
      final total = (event.data['total_files'] as num?)?.toDouble() ?? 1;
      state = state.copyWith(
        status: event.data['status'] as String? ?? 'Identifying',
        detail: '${processed.toInt()} / ${total.toInt()} files processed.',
        progress: total == 0 ? 0 : (processed / total).clamp(0, 1),
      );
    }
  }

  Future<void> _busy(String status, Future<void> Function() work) async {
    state = state.copyWith(busy: true, status: status, progress: 0, detail: '');
    try {
      await work();
    } catch (error) {
      _fail(error);
    } finally {
      state = state.copyWith(busy: false);
    }
  }

  void _fail(Object error) {
    state = state.copyWith(
      busy: false,
      status: 'Error',
      detail: error.toString(),
    );
  }
}
