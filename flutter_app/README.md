# Renameify

Flutter desktop frontend for Renameify. Windows is the supported target.
The app talks to the Python media-renaming core through `src/bridge/flutter_bridge.py`
in development and `renameify_bridge.exe` in installed builds.

## Development

```powershell
flutter pub get
flutter run -d windows
```

The Flutter UI includes the old app workflows: smart scanning, LLM provider/model
settings, custom prompts, Plex/Jellyfin/Emby presets, editable rename review,
metadata editing, history, and rollback.

## Verification

```powershell
flutter test
flutter analyze
flutter build windows
```

## Installer Build

Run from the repository root:

```powershell
build.bat installer
```

Build staging is written to `dist\app`. The installer is written directly under
`dist` as `Renameify-<version>-Setup.exe`.
