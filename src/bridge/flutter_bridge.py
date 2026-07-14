"""
JSON-lines bridge used by the Flutter frontend.

Protocol:
  input:  {"id":"op-1","command":"scan","payload":{"path":"C:/Media"}}
  output: {"id":"op-1","type":"progress","command":"scan","data":{...}}
  output: {"id":"op-1","type":"result","command":"scan","ok":true,"data":{...}}

Long-running commands execute on worker threads so a later "cancel" command can
interrupt scanner/LLM work through the existing cancellation token system.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.config import (
    add_recent_path,
    fetch_available_models,
    get_available_models,
    get_config_dir,
    get_platform_templates,
    get_recent_paths,
    load_config,
    save_config,
)
from core.gpt_service import (
    GPTProgress,
    MediaInfo,
    bind_cancel_token,
    identify_all_media,
    is_cancelled,
    request_cancel,
    reset_cancel,
    test_llm_connection,
)
from core.renamer import (
    RenamePlan,
    execute_rename_plan,
    execute_rollback,
    generate_rename_plan,
)
from core.rollback import RenameManifest, list_manifests, load_manifest
from core.scanner import MediaFile, ScanProgress, SubtitleFile, scan_directory
from utils.folder_filter import smart_filter_folders

try:
    from core.metadata import is_mutagen_available, read_metadata, write_metadata
except Exception:  # pragma: no cover - optional dependency path
    is_mutagen_available = None
    read_metadata = None
    write_metadata = None


LONG_COMMANDS = {
    "scan",
    "identify_plan",
    "apply_selected",
    "rollback",
    "test_connection",
    "models.fetch",
    "metadata.read",
    "metadata.write",
}


class FlutterBridge:
    """Stateful bridge process for one Flutter app session."""

    def __init__(self) -> None:
        self._write_lock = threading.Lock()
        self._plans: Dict[str, RenamePlan] = {}
        self._media_files: Dict[str, List[MediaFile]] = {}

    def serve(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                self._send_error(None, "unknown", f"Invalid JSON: {exc}")
                continue

            command = request.get("command", "")
            if command == "cancel":
                self._handle_sync(request)
            elif command in LONG_COMMANDS:
                thread = threading.Thread(target=self._handle_sync, args=(request,), daemon=True)
                thread.start()
            else:
                self._handle_sync(request)

    def _handle_sync(self, request: Dict[str, Any]) -> None:
        request_id = request.get("id")
        command = request.get("command", "")
        payload = request.get("payload") or {}

        try:
            if command in LONG_COMMANDS:
                token = reset_cancel()
                bind_cancel_token(token)
                self._send_event(request_id, "started", command, {"cancel_token": token})

            data = self._dispatch(command, payload, request_id)
            self._send_event(request_id, "result", command, data, ok=True)
        except InterruptedError:
            self._send_error(request_id, command, "Operation cancelled", code="cancelled")
        except Exception as exc:
            self._send_error(
                request_id,
                command,
                str(exc),
                code=exc.__class__.__name__,
                details=traceback.format_exc(),
            )

    def _dispatch(self, command: str, payload: Dict[str, Any], request_id: Optional[str]) -> Dict[str, Any]:
        if command == "config.load":
            return {"config": load_config()}
        if command == "config.save":
            config = load_config()
            incoming = payload.get("config") or {}
            config.update(incoming)
            if "platform" in incoming:
                config.update(get_platform_templates(config.get("platform", "generic")))
            save_config(config)
            return {"config": config}
        if command == "config.info":
            return {"config_dir": str(get_config_dir())}
        if command == "config.open_dir":
            os.startfile(get_config_dir())
            return {"opened": True, "config_dir": str(get_config_dir())}
        if command == "scan":
            return self._scan(payload, request_id)
        if command == "identify_plan":
            return self._identify_plan(payload, request_id)
        if command == "apply_selected":
            return self._apply_selected(payload)
        if command == "history":
            config = self._config_from_payload(payload)
            return {"manifests": [self._manifest_to_dict(m) for m in list_manifests(config)]}
        if command == "rollback":
            return self._rollback(payload)
        if command == "test_connection":
            return self._test_connection(payload)
        if command == "models.list":
            provider = payload.get("provider")
            return {"models": self._models_to_dicts(get_available_models(provider))}
        if command == "models.fetch":
            provider = payload.get("provider")
            api_key = payload.get("api_key")
            return {"models": self._models_to_dicts(fetch_available_models(provider, api_key))}
        if command == "metadata.available":
            return {"available": bool(is_mutagen_available and is_mutagen_available())}
        if command == "metadata.read":
            return self._read_metadata(payload)
        if command == "metadata.write":
            return self._write_metadata(payload)
        if command == "cancel":
            request_cancel()
            return {"cancelled": True}
        raise ValueError(f"Unsupported command: {command}")

    def _scan(self, payload: Dict[str, Any], request_id: Optional[str]) -> Dict[str, Any]:
        path = payload.get("path")
        if not path:
            raise ValueError("scan requires payload.path")

        config = self._config_from_payload(payload)
        folders_to_scan = None

        if config.get("smart_folder_filter", True):
            self._send_event(
                request_id,
                "progress",
                "scan",
                {
                    "folders_scanned": 0,
                    "files_found": 0,
                    "subtitles_found": 0,
                    "current_folder": "Classifying folders before scan",
                    "skipped_folders": 0,
                    "elapsed_seconds": 0,
                    "phase": "filtering",
                },
            )

            def filter_callback(message: str) -> None:
                self._send_event(
                    request_id,
                    "progress",
                    "scan",
                    {
                        "folders_scanned": 0,
                        "files_found": 0,
                        "subtitles_found": 0,
                        "current_folder": message,
                        "skipped_folders": 0,
                        "elapsed_seconds": 0,
                        "phase": "filtering",
                    },
                )

            folders_to_scan, _folders_to_skip, _classifications = smart_filter_folders(
                path,
                config=config,
                progress_callback=filter_callback,
                use_gpt=bool(config.get("openai_api_key")),
                should_cancel=is_cancelled,
            )
            if not folders_to_scan:
                folders_to_scan = None

        def progress_callback(progress: ScanProgress) -> None:
            self._send_event(request_id, "progress", "scan", asdict(progress))

        media_files = scan_directory(
            path,
            config,
            progress_callback=progress_callback,
            folders_to_scan=folders_to_scan,
            should_cancel=is_cancelled,
        )
        self._media_files[str(path)] = media_files
        add_recent_path(str(path))
        return {
            "path": path,
            "media_files": [self._media_file_to_dict(item) for item in media_files],
            "recent_paths": get_recent_paths(),
        }

    def _identify_plan(self, payload: Dict[str, Any], request_id: Optional[str]) -> Dict[str, Any]:
        path = payload.get("path")
        if not path:
            raise ValueError("identify_plan requires payload.path")

        config = self._config_from_payload(payload)
        media_files = self._media_files_from_payload(payload)
        if not media_files:
            media_files = self._media_files.get(str(path))
        if not media_files:
            media_files = scan_directory(path, config, should_cancel=is_cancelled)

        filenames_with_paths = [(item.filename + item.extension, str(item.path)) for item in media_files]

        def progress_callback(progress: GPTProgress) -> None:
            self._send_event(request_id, "progress", "identify_plan", asdict(progress))

        media_info = identify_all_media(
            filenames_with_paths,
            config,
            progress_callback=progress_callback,
            custom_prompt=payload.get("custom_prompt"),
            cancel_token=None,
        )
        plan = generate_rename_plan(media_files, media_info, str(path), config)
        self._plans[plan.manifest.id] = plan
        self._media_files[str(path)] = media_files
        return {
            "path": path,
            "media_info": [item.to_dict() for item in media_info],
            "plan": self._plan_to_dict(plan),
        }

    def _apply_selected(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        plan = self._plan_from_payload(payload)
        config = self._config_from_payload(payload)
        include_low = bool(payload.get("include_low_confidence", False))

        selected_operations = self._select_operations(plan.manifest.operations, payload)
        selected_folder_renames = self._select_folder_renames(plan.folder_renames, payload)

        manifest = RenameManifest(
            id=plan.manifest.id,
            timestamp=plan.manifest.timestamp,
            root_path=plan.manifest.root_path,
            total_operations=len(selected_operations),
            operations=selected_operations,
            applied=False,
            rolled_back=False,
            folder_renames=selected_folder_renames,
        )

        success, failed, errors = execute_rename_plan(
            manifest,
            include_low_confidence=include_low,
            config=config,
            folder_renames=selected_folder_renames,
        )
        return {
            "success": success,
            "failed": failed,
            "errors": errors,
            "manifest": self._manifest_to_dict(manifest),
        }

    def _rollback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        manifest_id = payload.get("manifest_id")
        if not manifest_id:
            raise ValueError("rollback requires payload.manifest_id")

        config = self._config_from_payload(payload)
        manifest = load_manifest(manifest_id, config)
        if manifest is None:
            raise FileNotFoundError(f"Manifest not found: {manifest_id}")

        success, failed, errors = execute_rollback(manifest, config)
        return {"success": success, "failed": failed, "errors": errors}

    def _test_connection(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        config = self._config_from_payload(payload)
        provider = payload.get("provider") or config.get("llm_provider", "openai")
        api_key = payload.get("api_key") or config.get(f"{provider}_api_key", "")
        model = payload.get("model") or config.get(f"{provider}_model")
        return test_llm_connection(provider, api_key, model, config)

    def _read_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if read_metadata is None:
            raise RuntimeError("Metadata support is not available")
        path = payload.get("path")
        if not path:
            raise ValueError("metadata.read requires payload.path")
        return {"metadata": read_metadata(path).to_dict()}

    def _write_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if write_metadata is None:
            raise RuntimeError("Metadata support is not available")
        path = payload.get("path")
        if not path:
            raise ValueError("metadata.write requires payload.path")
        updates = payload.get("updates") or {}
        return {"success": bool(write_metadata(path, updates))}

    def _plan_from_payload(self, payload: Dict[str, Any]) -> RenamePlan:
        plan_id = payload.get("plan_id")
        if plan_id and plan_id in self._plans:
            return self._plans[plan_id]

        plan_payload = payload.get("plan")
        if plan_payload:
            manifest = self._manifest_from_dict(plan_payload["manifest"])
            return RenamePlan(
                manifest=manifest,
                high_confidence=plan_payload.get("high_confidence", []),
                low_confidence=plan_payload.get("low_confidence", []),
                unknown=plan_payload.get("unknown", []),
                skipped=plan_payload.get("skipped", []),
                folder_renames=plan_payload.get("folder_renames", []),
            )

        raise ValueError("apply_selected requires payload.plan_id or payload.plan")

    def _config_from_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        config = load_config()
        config.update(payload.get("config") or {})
        return config

    def _media_files_from_payload(self, payload: Dict[str, Any]) -> List[MediaFile]:
        return [self._media_file_from_dict(item) for item in payload.get("media_files") or []]

    def _media_file_from_dict(self, item: Dict[str, Any]) -> MediaFile:
        subtitles = [
            SubtitleFile(
                path=Path(sub["path"]),
                filename=sub.get("filename") or Path(sub["path"]).stem,
                extension=sub.get("extension") or Path(sub["path"]).suffix,
                language=sub.get("language"),
            )
            for sub in item.get("subtitles", [])
        ]
        path = Path(item["path"])
        return MediaFile(
            path=path,
            filename=item.get("filename") or path.stem,
            extension=item.get("extension") or path.suffix,
            parent_folder=item.get("parent_folder") or path.parent.name,
            size_mb=float(item.get("size_mb") or 0),
            subtitles=subtitles,
        )

    def _media_file_to_dict(self, item: MediaFile) -> Dict[str, Any]:
        return {
            "path": str(item.path),
            "filename": item.filename,
            "extension": item.extension,
            "parent_folder": item.parent_folder,
            "size_mb": item.size_mb,
            "subtitles": [
                {
                    "path": str(sub.path),
                    "filename": sub.filename,
                    "extension": sub.extension,
                    "language": sub.language,
                }
                for sub in item.subtitles
            ],
        }

    def _manifest_from_dict(self, item: Dict[str, Any]) -> RenameManifest:
        return RenameManifest(
            id=item["id"],
            timestamp=item["timestamp"],
            root_path=item["root_path"],
            total_operations=item.get("total_operations", len(item.get("operations", []))),
            operations=item.get("operations", []),
            applied=bool(item.get("applied", False)),
            rolled_back=bool(item.get("rolled_back", False)),
            folder_renames=item.get("folder_renames", []),
        )

    def _manifest_to_dict(self, manifest: RenameManifest) -> Dict[str, Any]:
        return asdict(manifest)

    def _plan_to_dict(self, plan: RenamePlan) -> Dict[str, Any]:
        return {
            "manifest": self._manifest_to_dict(plan.manifest),
            "high_confidence": plan.high_confidence,
            "low_confidence": plan.low_confidence,
            "unknown": plan.unknown,
            "skipped": plan.skipped,
            "folder_renames": plan.folder_renames,
        }

    def _select_operations(self, operations: List[Dict[str, Any]], payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        indexes = payload.get("selected_operation_indexes")
        paths = set(payload.get("selected_operation_paths") or [])
        if indexes is not None:
            return [operations[int(index)] for index in indexes if 0 <= int(index) < len(operations)]
        if paths:
            return [op for op in operations if op.get("original_path") in paths]
        return list(operations)

    def _select_folder_renames(self, folder_renames: List[Dict[str, Any]], payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        indexes = payload.get("selected_folder_rename_indexes")
        if indexes is None:
            return list(folder_renames) if payload.get("include_folder_renames", True) else []
        return [folder_renames[int(index)] for index in indexes if 0 <= int(index) < len(folder_renames)]

    def _models_to_dicts(self, models: Iterable[Any]) -> List[Dict[str, Any]]:
        result = []
        for item in models:
            if isinstance(item, dict):
                model_id = str(item.get("id") or item.get("model") or "")
                description = str(item.get("description") or item.get("name") or model_id)
                result_item = {
                    "id": model_id,
                    "description": description,
                }
                for key in ("name", "detail", "cost_tier", "badge", "supports_web_search"):
                    if key in item:
                        result_item[key] = item[key]
            else:
                model_id = str(item[0])
                description = str(item[1]) if len(item) > 1 else model_id
                result_item = {"id": model_id, "description": description}
            result.append(result_item)
        return result

    def _send_event(
        self,
        request_id: Optional[str],
        event_type: str,
        command: str,
        data: Optional[Dict[str, Any]] = None,
        ok: Optional[bool] = None,
    ) -> None:
        event: Dict[str, Any] = {
            "id": request_id,
            "type": event_type,
            "command": command,
            "data": data or {},
        }
        if ok is not None:
            event["ok"] = ok
        with self._write_lock:
            print(json.dumps(event, ensure_ascii=False), flush=True)

    def _send_error(
        self,
        request_id: Optional[str],
        command: str,
        message: str,
        code: str = "error",
        details: Optional[str] = None,
    ) -> None:
        data = {"message": message, "code": code}
        if details:
            data["details"] = details
        self._send_event(request_id, "error", command, data, ok=False)


def main() -> None:
    FlutterBridge().serve()


if __name__ == "__main__":
    main()
