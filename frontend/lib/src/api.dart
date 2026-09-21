import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'models.dart';

Future<String?> selectLocalProject() => HttpEngineDocApi().selectProject();

abstract interface class EngineDocApi {
  Future<void> health();
  Future<AnalysisResult> analyzeProject(String projectPath);
  Future<List<AiModel>> listOpenRouterModels(String apiKey);
  Future<AiGenerationResult> generateAi(AiGenerationRequest request);
  Future<ExistingResults> existingResults(String xrayPath);
}

class HttpEngineDocApi implements EngineDocApi {
  HttpEngineDocApi({Uri? baseUri, http.Client? client})
    : baseUri =
          baseUri ?? (kIsWeb ? Uri.base : Uri.parse('http://127.0.0.1:8766')),
      _client = client ?? http.Client();
  final Uri baseUri;
  final http.Client _client;

  @override
  Future<void> health() async {
    await _request('GET', '/health');
  }

  Future<String?> selectProject() async {
    final result = await _request('POST', '/project/select', body: {});
    return result['project_path'] as String?;
  }

  Future<void> openOutput(String path) async {
    await _request('POST', '/output/open', body: {'path': path});
  }

  @override
  Future<AnalysisResult> analyzeProject(String projectPath) async =>
      AnalysisResult.fromJson(
        await _request('POST', '/analyze', body: {'project_path': projectPath}),
      );
  @override
  Future<List<AiModel>> listOpenRouterModels(String apiKey) async {
    final result = await _request(
      'POST',
      '/ai/openrouter/models',
      body: {'api_key': apiKey},
    );
    return (result['models'] as List)
        .map((m) => AiModel.fromJson(Map<String, dynamic>.from(m as Map)))
        .toList();
  }

  @override
  Future<AiGenerationResult> generateAi(AiGenerationRequest request) async =>
      AiGenerationResult.fromJson(
        await _request(
          'POST',
          '/ai/generate',
          body: {
            'mode': request.mode,
            'provider': request.provider,
            'api_key': request.apiKey,
            'xray_path': request.xrayPath,
            if (request.model != null) 'model': request.model,
          },
        ),
      );
  @override
  Future<ExistingResults> existingResults(String xrayPath) async =>
      ExistingResults.fromJson(
        await _request('POST', '/results', body: {'xray_path': xrayPath}),
      );

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    try {
      final request = http.Request(method, baseUri.resolve(path));
      request.headers['Content-Type'] = 'application/json; charset=utf-8';
      if (body != null) request.bodyBytes = utf8.encode(jsonEncode(body));
      final response = await (() async {
        final streamed = await _client.send(request);
        return http.Response.fromStream(streamed);
      })().timeout(const Duration(minutes: 10));
      final result =
          jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      if (response.statusCode >= 400) {
        final error = result['error'] as Map<String, dynamic>?;
        throw EngineDocApiException(
          error?['code'] as String? ?? 'backend_error',
          error?['message'] as String? ??
              'Não foi possível concluir a operação.',
        );
      }
      return result;
    } on EngineDocApiException {
      rethrow;
    } on TimeoutException {
      throw const EngineDocApiException(
        'timeout',
        'O processamento excedeu o tempo de espera. Tente novamente.',
      );
    } on http.ClientException {
      throw const EngineDocApiException(
        'connection',
        'A conexão local foi interrompida. Execute .\\app novamente.',
      );
    } on Object {
      throw const EngineDocApiException(
        'invalid_response',
        'Não foi possível ler a resposta do Engine Doc.',
      );
    }
  }
}
