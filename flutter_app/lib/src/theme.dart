import 'package:flutter/material.dart';

class RenameifyPalette {
  const RenameifyPalette({
    required this.black,
    required this.surface,
    required this.panel,
    required this.panelAlt,
    required this.gold,
    required this.goldSoft,
    required this.orange,
    required this.blue,
    required this.line,
    required this.text,
    required this.muted,
    required this.green,
    required this.red,
    required this.glow,
  });

  final Color black;
  final Color surface;
  final Color panel;
  final Color panelAlt;
  final Color gold;
  final Color goldSoft;
  final Color orange;
  final Color blue;
  final Color line;
  final Color text;
  final Color muted;
  final Color green;
  final Color red;
  final Color glow;

  Color get teal => gold;
  Color get tealSoft => goldSoft;
  Color get amber => gold;
}

class AppColors {
  static const dark = RenameifyPalette(
    black: Color(0xFF050506),
    surface: Color(0xFF0B0B0D),
    panel: Color(0xFF111113),
    panelAlt: Color(0xFF181715),
    gold: Color(0xFFF5B544),
    goldSoft: Color(0xFFFFD88A),
    orange: Color(0xFFFF8A2A),
    blue: Color(0xFF7AA8FF),
    line: Color(0xFF30291D),
    text: Color(0xFFF6F1E8),
    muted: Color(0xFFA79C8B),
    green: Color(0xFF4FC783),
    red: Color(0xFFE76D75),
    glow: Color(0x66F5B544),
  );

  static const light = RenameifyPalette(
    black: Color(0xFFF6F7FB),
    surface: Color(0xFFFFFFFF),
    panel: Color(0xFFFFFFFF),
    panelAlt: Color(0xFFF0F3F8),
    gold: Color(0xFFB87514),
    goldSoft: Color(0xFF7A4B05),
    orange: Color(0xFFD95F12),
    blue: Color(0xFF2E63C6),
    line: Color(0xFFD9DFEA),
    text: Color(0xFF15171C),
    muted: Color(0xFF667085),
    green: Color(0xFF16834A),
    red: Color(0xFFBF3645),
    glow: Color(0x22B87514),
  );

  // Startup and tests still need stable constants before a BuildContext exists.
  static const black = Color(0xFF050506);
}

extension RenameifyThemeColors on BuildContext {
  RenameifyPalette get colors =>
      Theme.of(this).brightness == Brightness.light
          ? AppColors.light
          : AppColors.dark;
}

ThemeMode themeModeFromConfig(Object? value) {
  return switch ('$value'.toLowerCase()) {
    'light' => ThemeMode.light,
    'system' => ThemeMode.system,
    _ => ThemeMode.dark,
  };
}

ThemeData buildRenameifyTheme(Brightness brightness) {
  final colors = brightness == Brightness.light ? AppColors.light : AppColors.dark;
  final scheme = ColorScheme.fromSeed(
    seedColor: colors.gold,
    brightness: brightness,
    surface: colors.panel,
    primary: colors.gold,
    secondary: colors.orange,
    error: colors.red,
  );

  final onPrimary =
      brightness == Brightness.light ? Colors.white : AppColors.dark.black;

  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    scaffoldBackgroundColor: colors.black,
    fontFamily: 'Segoe UI',
    textTheme: TextTheme(
      headlineMedium: TextStyle(
        color: colors.text,
        fontSize: 26,
        fontWeight: FontWeight.w700,
      ),
      titleLarge: TextStyle(
        color: colors.text,
        fontSize: 18,
        fontWeight: FontWeight.w700,
      ),
      titleMedium: TextStyle(
        color: colors.text,
        fontSize: 14,
        fontWeight: FontWeight.w700,
      ),
      bodyMedium: TextStyle(color: colors.text, fontSize: 13),
      bodySmall: TextStyle(color: colors.muted, fontSize: 12),
    ),
    iconTheme: IconThemeData(color: colors.muted),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: colors.panelAlt,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: colors.line),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: colors.line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: colors.gold),
      ),
      labelStyle: TextStyle(color: colors.muted),
      prefixIconColor: colors.goldSoft,
      suffixIconColor: colors.goldSoft,
    ),
    cardTheme: CardThemeData(
      color: colors.panel,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(color: colors.line),
      ),
    ),
    dataTableTheme: DataTableThemeData(
      headingRowColor: WidgetStateProperty.all(colors.panelAlt),
      dataRowColor: WidgetStateProperty.resolveWith(
        (states) =>
            states.contains(WidgetState.selected)
                ? colors.gold.withAlpha(24)
                : colors.panel,
      ),
      headingTextStyle: TextStyle(
        color: colors.goldSoft,
        fontWeight: FontWeight.w700,
        fontSize: 12,
      ),
      dataTextStyle: TextStyle(color: colors.text, fontSize: 12),
      dividerThickness: 0.6,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: colors.gold,
        foregroundColor: onPrimary,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: colors.goldSoft,
        side: BorderSide(color: colors.line),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: colors.panelAlt,
      selectedColor: colors.gold.withAlpha(32),
      side: BorderSide(color: colors.line),
      labelStyle: TextStyle(color: colors.text, fontSize: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith(
        (states) =>
            states.contains(WidgetState.selected) ? colors.gold : colors.muted,
      ),
      trackColor: WidgetStateProperty.resolveWith(
        (states) =>
            states.contains(WidgetState.selected)
                ? colors.gold.withAlpha(70)
                : colors.panelAlt,
      ),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: colors.gold,
      linearTrackColor: colors.panelAlt,
    ),
    dividerTheme: DividerThemeData(color: colors.line, thickness: 0.6),
    dialogTheme: DialogThemeData(
      backgroundColor: colors.panel,
      titleTextStyle: TextStyle(
        color: colors.text,
        fontSize: 18,
        fontWeight: FontWeight.w700,
      ),
      contentTextStyle: TextStyle(color: colors.text, fontSize: 13),
    ),
    popupMenuTheme: PopupMenuThemeData(
      color: colors.panel,
      textStyle: TextStyle(color: colors.text),
    ),
  );
}
