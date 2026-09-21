class AnalysisResult {
  const AnalysisResult({
    required this.projectName,
    required this.projectPath,
    required this.xrayPath,
    required this.outputDir,
    required this.content,
    required this.warnings,
  });

  factory AnalysisResult.fromJson(Map<String, dynamic> json) => AnalysisResult(
    projectName: json['project_name'] as String,
    projectPath: json['project_path'] as String,
    xrayPath: json['xray_path'] as String,
    outputDir: json['output_dir'] as String,
    content: json['content'] as String,
    warnings: (json['warnings'] as List<dynamic>? ?? const [])
        .whereType<String>()
        .toList(growable: false),
  );

  final String projectName;
  final String projectPath;
  final String xrayPath;
  final String outputDir;
  final String content;
  final List<String> warnings;
}

class AiModel {
  const AiModel({
    required this.id,
    required this.name,
    required this.automatic,
    this.contextLength,
  });

  factory AiModel.fromJson(Map<String, dynamic> json) => AiModel(
    id: json['id'] as String,
    name: json['name'] as String,
    automatic: json['automatic'] as bool? ?? false,
    contextLength: json['context_length'] as int?,
  );

  final String id;
  final String name;
  final bool automatic;
  final int? contextLength;
}

class AiGenerationRequest {
  const AiGenerationRequest({
    required this.mode,
    required this.provider,
    required this.apiKey,
    required this.xrayPath,
    this.model,
  });

  final String mode;
  final String provider;
  final String apiKey;
  final String xrayPath;
  final String? model;
}

class AiGenerationResult {
  const AiGenerationResult({
    required this.type,
    required this.provider,
    required this.model,
    required this.outputPath,
    required this.outputDir,
    required this.content,
  });

  factory AiGenerationResult.fromJson(Map<String, dynamic> json) =>
      AiGenerationResult(
        type: json['type'] as String,
        provider: json['provider'] as String,
        model: json['model'] as String,
        outputPath: json['output_path'] as String,
        outputDir: json['output_dir'] as String,
        content: json['content'] as String,
      );

  final String type;
  final String provider;
  final String model;
  final String outputPath;
  final String outputDir;
  final String content;
}

class StoredResult {
  const StoredResult({required this.outputPath, required this.content});

  factory StoredResult.fromJson(Map<String, dynamic> json) => StoredResult(
    outputPath: json['output_path'] as String,
    content: json['content'] as String,
  );

  final String outputPath;
  final String content;
}

class ExistingResults {
  const ExistingResults({this.criticalAnalysis, this.documentation});

  factory ExistingResults.fromJson(Map<String, dynamic> json) =>
      ExistingResults(
        criticalAnalysis: json['critical_analysis'] is Map<String, dynamic>
            ? StoredResult.fromJson(
                json['critical_analysis'] as Map<String, dynamic>,
              )
            : null,
        documentation: json['documentation'] is Map<String, dynamic>
            ? StoredResult.fromJson(
                json['documentation'] as Map<String, dynamic>,
              )
            : null,
      );

  final StoredResult? criticalAnalysis;
  final StoredResult? documentation;
}

class EngineDocApiException implements Exception {
  const EngineDocApiException(this.code, this.message);

  final String code;
  final String message;

  @override
  String toString() => message;
}
