import 'dart:convert';

class BridgeEvent {
  const BridgeEvent({
    required this.id,
    required this.type,
    required this.command,
    required this.data,
    this.ok,
  });

  final String? id;
  final String type;
  final String command;
  final Map<String, dynamic> data;
  final bool? ok;

  factory BridgeEvent.fromJson(Map<String, dynamic> json) {
    return BridgeEvent(
      id: json['id'] as String?,
      type: json['type'] as String? ?? 'unknown',
      command: json['command'] as String? ?? 'unknown',
      data: (json['data'] as Map?)?.cast<String, dynamic>() ?? {},
      ok: json['ok'] as bool?,
    );
  }

  static BridgeEvent parseLine(String line) {
    return BridgeEvent.fromJson(jsonDecode(line) as Map<String, dynamic>);
  }
}

class MediaFileModel {
  const MediaFileModel({
    required this.path,
    required this.filename,
    required this.extension,
    required this.parentFolder,
    required this.sizeMb,
    this.subtitles = const [],
  });

  final String path;
  final String filename;
  final String extension;
  final String parentFolder;
  final double sizeMb;
  final List<SubtitleModel> subtitles;

  factory MediaFileModel.fromJson(Map<String, dynamic> json) {
    return MediaFileModel(
      path: json['path'] as String? ?? '',
      filename: json['filename'] as String? ?? '',
      extension: json['extension'] as String? ?? '',
      parentFolder: json['parent_folder'] as String? ?? '',
      sizeMb: (json['size_mb'] as num?)?.toDouble() ?? 0,
      subtitles:
          (json['subtitles'] as List? ?? const [])
              .map(
                (item) => SubtitleModel.fromJson(
                  (item as Map).cast<String, dynamic>(),
                ),
              )
              .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'path': path,
      'filename': filename,
      'extension': extension,
      'parent_folder': parentFolder,
      'size_mb': sizeMb,
      'subtitles': subtitles.map((item) => item.toJson()).toList(),
    };
  }
}

class SubtitleModel {
  const SubtitleModel({
    required this.path,
    required this.filename,
    required this.extension,
    this.language,
  });

  final String path;
  final String filename;
  final String extension;
  final String? language;

  factory SubtitleModel.fromJson(Map<String, dynamic> json) {
    return SubtitleModel(
      path: json['path'] as String? ?? '',
      filename: json['filename'] as String? ?? '',
      extension: json['extension'] as String? ?? '',
      language: json['language'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'path': path,
      'filename': filename,
      'extension': extension,
      'language': language,
    };
  }
}

class ManifestModel {
  const ManifestModel({
    required this.id,
    required this.rootPath,
    required this.operations,
    required this.folderRenames,
    required this.applied,
    required this.rolledBack,
  });

  final String id;
  final String rootPath;
  final List<Map<String, dynamic>> operations;
  final List<Map<String, dynamic>> folderRenames;
  final bool applied;
  final bool rolledBack;

  factory ManifestModel.fromJson(Map<String, dynamic> json) {
    return ManifestModel(
      id: json['id'] as String? ?? '',
      rootPath: json['root_path'] as String? ?? '',
      operations: _listOfMaps(json['operations']),
      folderRenames: _listOfMaps(json['folder_renames']),
      applied: json['applied'] as bool? ?? false,
      rolledBack: json['rolled_back'] as bool? ?? false,
    );
  }
}

class PlanModel {
  const PlanModel({
    required this.manifest,
    required this.highConfidence,
    required this.lowConfidence,
    required this.unknown,
    required this.skipped,
    required this.folderRenames,
  });

  final ManifestModel manifest;
  final List<Map<String, dynamic>> highConfidence;
  final List<Map<String, dynamic>> lowConfidence;
  final List<Map<String, dynamic>> unknown;
  final List<Map<String, dynamic>> skipped;
  final List<Map<String, dynamic>> folderRenames;

  factory PlanModel.fromJson(Map<String, dynamic> json) {
    return PlanModel(
      manifest: ManifestModel.fromJson(
        (json['manifest'] as Map?)?.cast<String, dynamic>() ?? {},
      ),
      highConfidence: _listOfMaps(json['high_confidence']),
      lowConfidence: _listOfMaps(json['low_confidence']),
      unknown: _listOfMaps(json['unknown']),
      skipped: _listOfMaps(json['skipped']),
      folderRenames: _listOfMaps(json['folder_renames']),
    );
  }

  List<PlanRowModel> get rows {
    final rows = <PlanRowModel>[];
    final opIndexByPath = <String, int>{};
    for (var i = 0; i < manifest.operations.length; i++) {
      final path = manifest.operations[i]['original_path'] as String?;
      if (path != null) {
        opIndexByPath[path] = i;
      }
    }

    void addRows(List<Map<String, dynamic>> items, String bucket) {
      for (final item in items) {
        final original = item['original_path'] as String? ?? '';
        rows.add(
          PlanRowModel(
            bucket: bucket,
            operationIndex: opIndexByPath[original],
            originalPath: original,
            newPath: item['new_path'] as String? ?? '',
            mediaType: item['media_type'] as String? ?? '',
            confidence: item['confidence'] as int? ?? 0,
            notes: item['notes'] as String?,
            isFolderRename: false,
          ),
        );
      }
    }

    addRows(highConfidence, 'High');
    addRows(lowConfidence, 'Low');
    addRows(unknown, 'Unknown');

    for (var i = 0; i < folderRenames.length; i++) {
      final item = folderRenames[i];
      rows.add(
        PlanRowModel(
          bucket: 'Folder',
          folderRenameIndex: i,
          originalPath: item['original_path'] as String? ?? '',
          newPath: item['new_path'] as String? ?? '',
          mediaType: item['type'] as String? ?? 'folder',
          confidence: item['confidence'] as int? ?? 0,
          notes: 'Folder rename',
          isFolderRename: true,
        ),
      );
    }
    return rows;
  }

  PlanModel withEditedNewPath(String originalPath, String editedName) {
    String rewritePath(String oldPath) {
      if (oldPath.isEmpty || editedName.trim().isEmpty) {
        return oldPath;
      }
      final separator = oldPath.contains('\\') ? '\\' : '/';
      final index = oldPath.replaceAll('\\', '/').lastIndexOf('/');
      if (index == -1) {
        return editedName;
      }
      final prefix = oldPath.substring(
        0,
        oldPath.length - basename(oldPath).length,
      );
      var nextName = editedName.trim();
      if (!nextName.contains('.') && basename(oldPath).contains('.')) {
        final current = basename(oldPath);
        final dot = current.lastIndexOf('.');
        if (dot != -1) {
          nextName = '$nextName${current.substring(dot)}';
        }
      }
      return prefix.endsWith(separator)
          ? '$prefix$nextName'
          : '$prefix$separator$nextName';
    }

    Map<String, dynamic> updateItem(Map<String, dynamic> item) {
      if (item['original_path'] != originalPath) {
        return {...item};
      }
      return {
        ...item,
        'new_path': rewritePath(item['new_path'] as String? ?? ''),
      };
    }

    final operations = [for (final op in manifest.operations) updateItem(op)];
    final nextManifest = ManifestModel(
      id: manifest.id,
      rootPath: manifest.rootPath,
      operations: operations,
      folderRenames: manifest.folderRenames,
      applied: manifest.applied,
      rolledBack: manifest.rolledBack,
    );

    return PlanModel(
      manifest: nextManifest,
      highConfidence: [for (final item in highConfidence) updateItem(item)],
      lowConfidence: [for (final item in lowConfidence) updateItem(item)],
      unknown: [for (final item in unknown) updateItem(item)],
      skipped: skipped,
      folderRenames: folderRenames,
    );
  }

  PlanModel withEditedFolderPath(int index, String editedName) {
    final nextFolderRenames = <Map<String, dynamic>>[];
    for (var i = 0; i < folderRenames.length; i++) {
      final item = folderRenames[i];
      if (i != index) {
        nextFolderRenames.add({...item});
        continue;
      }
      final oldNewPath = item['new_path'] as String? ?? '';
      final prefix = oldNewPath.substring(
        0,
        oldNewPath.length - basename(oldNewPath).length,
      );
      nextFolderRenames.add({
        ...item,
        'new_name': editedName.trim(),
        'new_path': '$prefix${editedName.trim()}',
      });
    }
    return PlanModel(
      manifest: manifest,
      highConfidence: highConfidence,
      lowConfidence: lowConfidence,
      unknown: unknown,
      skipped: skipped,
      folderRenames: nextFolderRenames,
    );
  }
}

class PlanRowModel {
  const PlanRowModel({
    required this.bucket,
    required this.originalPath,
    required this.newPath,
    required this.mediaType,
    required this.confidence,
    required this.isFolderRename,
    this.operationIndex,
    this.folderRenameIndex,
    this.notes,
  });

  final String bucket;
  final int? operationIndex;
  final int? folderRenameIndex;
  final String originalPath;
  final String newPath;
  final String mediaType;
  final int confidence;
  final String? notes;
  final bool isFolderRename;

  String get originalName => basename(originalPath);
  String get newName => basename(newPath);
}

class RenameifyState {
  const RenameifyState({
    required this.selectedPath,
    required this.status,
    required this.detail,
    required this.progress,
    required this.busy,
    required this.config,
    required this.mediaFiles,
    required this.history,
    required this.selectedOperationPaths,
    required this.selectedFolderRenameIndexes,
    required this.includeLowConfidence,
    required this.renameFolders,
    required this.models,
    required this.configDir,
    this.metadata,
    this.plan,
  });

  factory RenameifyState.initial() {
    return const RenameifyState(
      selectedPath: '',
      status: 'Ready',
      detail: 'Select a media folder to begin.',
      progress: 0,
      busy: false,
      config: {},
      mediaFiles: [],
      history: [],
      selectedOperationPaths: {},
      selectedFolderRenameIndexes: {},
      includeLowConfidence: false,
      renameFolders: true,
      models: [],
      configDir: '',
    );
  }

  final String selectedPath;
  final String status;
  final String detail;
  final double progress;
  final bool busy;
  final Map<String, dynamic> config;
  final List<MediaFileModel> mediaFiles;
  final PlanModel? plan;
  final List<Map<String, dynamic>> history;
  final Set<String> selectedOperationPaths;
  final Set<int> selectedFolderRenameIndexes;
  final bool includeLowConfidence;
  final bool renameFolders;
  final List<ModelOption> models;
  final String configDir;
  final FileMetadataModel? metadata;

  int get selectedCount =>
      selectedOperationPaths.length + selectedFolderRenameIndexes.length;

  RenameifyState copyWith({
    String? selectedPath,
    String? status,
    String? detail,
    double? progress,
    bool? busy,
    Map<String, dynamic>? config,
    List<MediaFileModel>? mediaFiles,
    PlanModel? plan,
    bool clearPlan = false,
    List<Map<String, dynamic>>? history,
    Set<String>? selectedOperationPaths,
    Set<int>? selectedFolderRenameIndexes,
    bool? includeLowConfidence,
    bool? renameFolders,
    List<ModelOption>? models,
    String? configDir,
    FileMetadataModel? metadata,
    bool clearMetadata = false,
  }) {
    return RenameifyState(
      selectedPath: selectedPath ?? this.selectedPath,
      status: status ?? this.status,
      detail: detail ?? this.detail,
      progress: progress ?? this.progress,
      busy: busy ?? this.busy,
      config: config ?? this.config,
      mediaFiles: mediaFiles ?? this.mediaFiles,
      plan: clearPlan ? null : (plan ?? this.plan),
      history: history ?? this.history,
      selectedOperationPaths:
          selectedOperationPaths ?? this.selectedOperationPaths,
      selectedFolderRenameIndexes:
          selectedFolderRenameIndexes ?? this.selectedFolderRenameIndexes,
      includeLowConfidence: includeLowConfidence ?? this.includeLowConfidence,
      renameFolders: renameFolders ?? this.renameFolders,
      models: models ?? this.models,
      configDir: configDir ?? this.configDir,
      metadata: clearMetadata ? null : (metadata ?? this.metadata),
    );
  }
}

class ModelOption {
  const ModelOption({
    required this.id,
    required this.description,
    this.name = '',
    this.detail = '',
    this.costTier = '',
    this.badge = '',
    this.supportsWebSearch = false,
  });

  final String id;
  final String description;
  final String name;
  final String detail;
  final String costTier;
  final String badge;
  final bool supportsWebSearch;

  factory ModelOption.fromJson(Map<String, dynamic> json) {
    return ModelOption(
      id: json['id'] as String? ?? '',
      description: json['description'] as String? ?? '',
      name: json['name'] as String? ?? '',
      detail: json['detail'] as String? ?? '',
      costTier: json['cost_tier'] as String? ?? '',
      badge: json['badge'] as String? ?? '',
      supportsWebSearch: json['supports_web_search'] as bool? ?? false,
    );
  }

  String get title => name.isEmpty ? description : name;

  String get label =>
      description.isEmpty || description == id ? id : '$title - $id';
}

class FileMetadataModel {
  const FileMetadataModel({
    required this.filePath,
    required this.fileType,
    required this.values,
    required this.raw,
    required this.hasMetadata,
    required this.isReadable,
    this.error,
  });

  final String filePath;
  final String fileType;
  final Map<String, dynamic> values;
  final Map<String, dynamic> raw;
  final bool hasMetadata;
  final bool isReadable;
  final String? error;

  factory FileMetadataModel.fromJson(Map<String, dynamic> json) {
    final editable = <String, dynamic>{};
    const fields = [
      'title',
      'artist',
      'album',
      'year',
      'genre',
      'track_number',
      'total_tracks',
      'disc_number',
      'comment',
      'show_name',
      'season',
      'episode',
      'episode_title',
      'album_artist',
      'composer',
    ];
    for (final field in fields) {
      if (json.containsKey(field)) {
        editable[field] = json[field];
      }
    }

    return FileMetadataModel(
      filePath: json['file_path'] as String? ?? '',
      fileType: json['file_type'] as String? ?? 'unknown',
      values: editable,
      raw: (json['raw'] as Map?)?.cast<String, dynamic>() ?? {},
      hasMetadata: json['has_metadata'] as bool? ?? false,
      isReadable: json['is_readable'] as bool? ?? true,
      error: json['error'] as String?,
    );
  }
}

List<Map<String, dynamic>> _listOfMaps(Object? value) {
  return (value as List? ?? const [])
      .map((item) => (item as Map).cast<String, dynamic>())
      .toList();
}

String basename(String path) {
  if (path.isEmpty) {
    return '';
  }
  final normalized = path.replaceAll('\\', '/');
  final slash = normalized.lastIndexOf('/');
  return slash == -1 ? normalized : normalized.substring(slash + 1);
}
