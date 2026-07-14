import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/src/app_controller.dart';
import 'package:flutter_app/src/bridge_client.dart';
import 'package:flutter_app/src/models.dart';

void main() {
  test('BridgeEvent parses JSONL events', () {
    final event = BridgeEvent.parseLine(
      jsonEncode({
        'id': 'op-1',
        'type': 'progress',
        'command': 'scan',
        'data': {'files_found': 3},
      }),
    );

    expect(event.id, 'op-1');
    expect(event.type, 'progress');
    expect(event.command, 'scan');
    expect(event.data['files_found'], 3);
  });

  test('scan and identify update review state', () async {
    final fake = FakeBridgeClient({
      'scan': {
        'media_files': [
          {
            'path': 'C:/Media/a.mkv',
            'filename': 'a',
            'extension': '.mkv',
            'parent_folder': 'Media',
            'size_mb': 10.0,
          },
        ],
      },
      'identify_plan': {'plan': samplePlan()},
    });
    final container = ProviderContainer(
      overrides: [bridgeClientProvider.overrideWithValue(fake)],
    );
    addTearDown(container.dispose);

    final controller = container.read(appControllerProvider.notifier);
    controller.setPath('C:/Media');
    await controller.scan();
    await controller.identifyPlan();

    final state = container.read(appControllerProvider);
    expect(state.mediaFiles, hasLength(1));
    expect(state.plan, isNotNull);
    expect(state.selectedOperationPaths, contains('C:/Media/a.mkv'));
    expect(state.selectedOperationPaths, isNot(contains('C:/Media/b.mkv')));
    expect(state.selectedFolderRenameIndexes, contains(0));
  });

  test('applySelected sends only selected operations and folders', () async {
    final fake = FakeBridgeClient({
      'identify_plan': {'plan': samplePlan()},
      'apply_selected': {'success': 1, 'failed': 0, 'errors': []},
      'history': {'manifests': []},
    });
    final container = ProviderContainer(
      overrides: [bridgeClientProvider.overrideWithValue(fake)],
    );
    addTearDown(container.dispose);

    final controller = container.read(appControllerProvider.notifier);
    controller.setPath('C:/Media');
    controller.setIncludeLowConfidence(true);
    await controller.identifyPlan();

    final plan = container.read(appControllerProvider).plan!;
    controller.toggleRow(plan.rows.first, false);
    await controller.applySelected();

    final apply = fake.sent.lastWhere(
      (item) => item.command == 'apply_selected',
    );
    expect(apply.payload['selected_operation_paths'], ['C:/Media/b.mkv']);
    expect(apply.payload['selected_folder_rename_indexes'], [0]);
  });
}

Map<String, dynamic> samplePlan() {
  return {
    'manifest': {
      'id': 'plan-1',
      'timestamp': '2026-05-05T00:00:00',
      'root_path': 'C:/Media',
      'operations': [
        {
          'original_path': 'C:/Media/a.mkv',
          'new_path': 'C:/Media/A (2020).mkv',
          'media_type': 'movie',
          'confidence': 95,
          'title': 'A',
        },
        {
          'original_path': 'C:/Media/b.mkv',
          'new_path': 'C:/Media/B (2021).mkv',
          'media_type': 'movie',
          'confidence': 70,
          'title': 'B',
        },
      ],
      'applied': false,
      'rolled_back': false,
      'folder_renames': [
        {
          'original_path': 'C:/Media/Old',
          'new_path': 'C:/Media/New',
          'type': 'movie_folder',
          'confidence': 90,
        },
      ],
    },
    'high_confidence': [
      {
        'original_path': 'C:/Media/a.mkv',
        'new_path': 'C:/Media/A (2020).mkv',
        'media_type': 'movie',
        'confidence': 95,
        'notes': null,
      },
    ],
    'low_confidence': [
      {
        'original_path': 'C:/Media/b.mkv',
        'new_path': 'C:/Media/B (2021).mkv',
        'media_type': 'movie',
        'confidence': 70,
        'notes': 'Review',
      },
    ],
    'unknown': [],
    'skipped': [],
    'folder_renames': [
      {
        'original_path': 'C:/Media/Old',
        'new_path': 'C:/Media/New',
        'type': 'movie_folder',
        'confidence': 90,
      },
    ],
  };
}

class SentCommand {
  const SentCommand(this.command, this.payload);

  final String command;
  final Map<String, dynamic> payload;
}

class FakeBridgeClient implements BridgeClient {
  FakeBridgeClient(this.responses);

  final Map<String, Map<String, dynamic>> responses;
  final sent = <SentCommand>[];
  final _events = StreamController<BridgeEvent>.broadcast();

  @override
  Stream<BridgeEvent> get events => _events.stream;

  @override
  Future<BridgeEvent> send(String command, Map<String, dynamic> payload) async {
    sent.add(SentCommand(command, payload));
    return BridgeEvent(
      id: 'fake',
      type: 'result',
      command: command,
      data: responses[command] ?? {},
      ok: true,
    );
  }

  @override
  void dispose() {
    _events.close();
  }
}
