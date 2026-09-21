import 'package:engine_doc_desktop/src/api.dart';
import 'package:engine_doc_desktop/src/app.dart';
import 'package:engine_doc_desktop/src/models.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeEngineDocApi implements EngineDocApi {
  FakeEngineDocApi({this.analysisError});

  final EngineDocApiException? analysisError;

  @override
  Future<void> health() async {}

  @override
  Future<AnalysisResult> analyzeProject(String projectPath) async {
    if (analysisError != null) throw analysisError!;
    return AnalysisResult(
      projectName: 'Sales',
      projectPath: projectPath,
      xrayPath: r'C:\output\Sales\Sales_raio_x.txt',
      outputDir: r'C:\output\Sales',
      content: 'RAIO-X DO PROJETO\nMEDIDA: Sales[Total Sales]\nRELACIONAMENTOS',
      warnings: const [],
    );
  }

  @override
  Future<ExistingResults> existingResults(String xrayPath) async =>
      const ExistingResults();

  @override
  Future<List<AiModel>> listOpenRouterModels(String apiKey) async => const [
    AiModel(
      id: 'openrouter/free',
      name: 'OpenRouter Free Router',
      automatic: true,
      contextLength: 131072,
    ),
  ];

  @override
  Future<AiGenerationResult> generateAi(AiGenerationRequest request) async =>
      const AiGenerationResult(
        type: 'critical_analysis',
        provider: 'NVIDIA NIM',
        model: 'nvidia/test',
        outputPath: r'C:\output\Sales\Sales_raio_x_analise_ia.txt',
        outputDir: r'C:\output\Sales',
        content: 'ANÁLISE TÉCNICA POR IA',
      );
}

void main() {
  Future<void> configureWindow(WidgetTester tester) async {
    tester.view.physicalSize = const Size(1440, 950);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  EngineDocApp app(EngineDocApi api) => EngineDocApp(
    api: api,
    directoryPicker: () async => r'C:\demo\Sales',
    pathOpener: (_) async {},
  );

  testWidgets('exibe o estado inicial sem projeto', (tester) async {
    await configureWindow(tester);
    await tester.pumpWidget(app(FakeEngineDocApi()));

    expect(find.text('Selecione seu projeto'), findsOneWidget);
    expect(find.text('Selecionar pasta'), findsOneWidget);
    expect(find.text('Analisar projeto'), findsNothing);
  });

  testWidgets('seleciona projeto, analisa e mostra o raio-x', (tester) async {
    await configureWindow(tester);
    await tester.pumpWidget(app(FakeEngineDocApi()));

    await tester.tap(find.text('Selecionar pasta'));
    await tester.pump();
    expect(find.text('Projeto selecionado'), findsOneWidget);

    await tester.tap(find.byKey(const Key('analyze-button')));
    await tester.pumpAndSettle();

    expect(find.text('Sales'), findsOneWidget);
    expect(find.textContaining('RAIO-X DO PROJETO'), findsOneWidget);
    expect(find.byKey(const Key('document-search')), findsOneWidget);
  });

  testWidgets('mostra erro amigável retornado pelo backend', (tester) async {
    await configureWindow(tester);
    await tester.pumpWidget(
      app(
        FakeEngineDocApi(
          analysisError: const EngineDocApiException(
            'invalid_project',
            'Não foi possível identificar um projeto PBIP compatível nesta pasta.',
          ),
        ),
      ),
    );

    await tester.tap(find.text('Selecionar pasta'));
    await tester.pump();
    await tester.tap(find.byKey(const Key('analyze-button')));
    await tester.pumpAndSettle();

    expect(find.textContaining('projeto PBIP compatível'), findsOneWidget);
  });

  testWidgets('abre o fluxo de IA com modos e providers existentes', (
    tester,
  ) async {
    await configureWindow(tester);
    await tester.pumpWidget(app(FakeEngineDocApi()));
    await tester.tap(find.text('Selecionar pasta'));
    await tester.pump();
    await tester.tap(find.byKey(const Key('analyze-button')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('generate-ai-button')));
    await tester.pumpAndSettle();
    expect(find.text('Análise crítica'), findsWidgets);
    expect(find.text('Documentação executiva/técnica'), findsOneWidget);

    await tester.tap(find.text('Continuar'));
    await tester.pumpAndSettle();
    expect(find.text('NVIDIA NIM'), findsOneWidget);
    expect(find.text('OpenRouter'), findsOneWidget);
  });
}
