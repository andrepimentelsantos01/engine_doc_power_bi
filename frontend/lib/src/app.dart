import 'package:flutter/material.dart';

import 'api.dart';
import 'home_page.dart';

class EngineDocApp extends StatelessWidget {
  EngineDocApp({
    EngineDocApi? api,
    this.directoryPicker,
    this.pathOpener,
    super.key,
  }) : api = api ?? HttpEngineDocApi();

  final EngineDocApi api;
  final DirectoryPicker? directoryPicker;
  final NativePathOpener? pathOpener;

  @override
  Widget build(BuildContext context) {
    const navy = Color(0xFF14233B);
    const gold = Color(0xFFF2C811);
    final scheme =
        ColorScheme.fromSeed(
          seedColor: navy,
          brightness: Brightness.light,
          surface: Colors.white,
        ).copyWith(
          primary: navy,
          secondary: gold,
          primaryContainer: const Color(0xFFE7EDF5),
          secondaryContainer: const Color(0xFFFFF3B8),
          surfaceContainerLowest: const Color(0xFFF7F8FA),
        );

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Engine Doc Power BI',
      theme: ThemeData(
        colorScheme: scheme,
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF3F5F8),
        fontFamily: 'Segoe UI',
        appBarTheme: const AppBarTheme(
          backgroundColor: navy,
          foregroundColor: Colors.white,
          elevation: 0,
          titleTextStyle: TextStyle(
            fontFamily: 'Segoe UI',
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.w700,
            letterSpacing: .3,
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          isDense: true,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: BorderSide(color: scheme.outlineVariant),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: BorderSide(color: scheme.outlineVariant),
          ),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
          ),
        ),
        dialogTheme: DialogThemeData(
          backgroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
        ),
      ),
      home: EngineDocHomePage(
        api: api,
        directoryPicker: directoryPicker,
        pathOpener: pathOpener,
      ),
    );
  }
}
