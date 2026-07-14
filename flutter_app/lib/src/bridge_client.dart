import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'models.dart';

final bridgeClientProvider = Provider<BridgeClient>((ref) {
  final client = RenameifyBridgeClient();
  ref.onDispose(client.dispose);
  return client;
});

abstract class BridgeClient {
  Stream<BridgeEvent> get events;

  Future<BridgeEvent> send(String command, Map<String, dynamic> payload);

  void dispose();
}

class BridgeException implements Exception {
  const BridgeException(this.message, {this.code});

  final String message;
  final String? code;

  @override
  String toString() => code == null ? message : '$code: $message';
}

class RenameifyBridgeClient implements BridgeClient {
  final _events = StreamController<BridgeEvent>.broadcast();
  final _pending = <String, Completer<BridgeEvent>>{};
  Process? _process;
  int _nextId = 0;

  @override
  Stream<BridgeEvent> get events => _events.stream;

  @override
  Future<BridgeEvent> send(String command, Map<String, dynamic> payload) async {
    final process = await _ensureProcess();
    final id = 'flutter-${++_nextId}';
    final completer = Completer<BridgeEvent>();
    _pending[id] = completer;

    process.stdin.writeln(
      jsonEncode({'id': id, 'command': command, 'payload': payload}),
    );

    return completer.future;
  }

  Future<Process> _ensureProcess() async {
    final running = _process;
    if (running != null) {
      return running;
    }

    final launch = _findBridgeLaunch();
    final process = await Process.start(
      launch.executable,
      launch.arguments,
      workingDirectory: launch.workingDirectory,
      runInShell: Platform.isWindows,
    );
    _process = process;

    process.stdout
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen(_handleLine);
    process.stderr
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen((line) {
          _events.add(
            BridgeEvent(
              id: null,
              type: 'stderr',
              command: 'bridge',
              data: {'message': line},
            ),
          );
        });
    process.exitCode.then((code) {
      final error = BridgeException('Bridge exited with code $code');
      for (final completer in _pending.values) {
        if (!completer.isCompleted) {
          completer.completeError(error);
        }
      }
      _pending.clear();
      _process = null;
    });

    return process;
  }

  void _handleLine(String line) {
    final event = BridgeEvent.parseLine(line);
    _events.add(event);

    final id = event.id;
    if (id == null) {
      return;
    }
    final completer = _pending[id];
    if (completer == null) {
      return;
    }

    if (event.type == 'result') {
      _pending.remove(id);
      completer.complete(event);
    } else if (event.type == 'error') {
      _pending.remove(id);
      completer.completeError(
        BridgeException(
          event.data['message'] as String? ?? 'Bridge command failed',
          code: event.data['code'] as String?,
        ),
      );
    }
  }

  _BridgeLaunch _findBridgeLaunch() {
    final current = Directory.current;
    final executableDir = File(Platform.resolvedExecutable).parent;
    final candidates = <Directory>[
      current,
      current.parent,
      executableDir,
      executableDir.parent,
    ];

    for (final dir in candidates) {
      final exe = File(
        '${dir.path}${Platform.pathSeparator}renameify_bridge.exe',
      );
      if (exe.existsSync()) {
        return _BridgeLaunch(exe.path, const [], dir.path);
      }
    }

    for (final dir in candidates) {
      final script = File(
        '${dir.path}${Platform.pathSeparator}src'
        '${Platform.pathSeparator}bridge'
        '${Platform.pathSeparator}flutter_bridge.py',
      );
      if (script.existsSync()) {
        return _BridgeLaunch(Platform.isWindows ? 'python' : 'python3', [
          script.path,
        ], dir.path);
      }
    }

    throw const BridgeException(
      'Could not find renameify_bridge.exe or src/bridge/flutter_bridge.py',
      code: 'bridge_not_found',
    );
  }

  @override
  void dispose() {
    for (final completer in _pending.values) {
      if (!completer.isCompleted) {
        completer.completeError(const BridgeException('Bridge disposed'));
      }
    }
    _pending.clear();
    _process?.kill();
    _events.close();
  }
}

class _BridgeLaunch {
  const _BridgeLaunch(this.executable, this.arguments, this.workingDirectory);

  final String executable;
  final List<String> arguments;
  final String workingDirectory;
}
