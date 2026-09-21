import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'ai_dialog.dart';
import 'api.dart';
import 'models.dart';

typedef DirectoryPicker = Future<String?> Function();
typedef NativePathOpener = Future<void> Function(String path);

enum DocumentView { xray, criticalAnalysis, documentation }

class EngineDocHomePage extends StatefulWidget {
  const EngineDocHomePage({
    required this.api,
    DirectoryPicker? directoryPicker,
    NativePathOpener? pathOpener,
    super.key,
  }) : directoryPicker = directoryPicker ?? selectLocalProject,
       pathOpener = pathOpener ?? _openNativePath;

  final EngineDocApi api;
  final DirectoryPicker directoryPicker;
  final NativePathOpener pathOpener;

  static Future<void> _openNativePath(String path) async {
    await HttpEngineDocApi().openOutput(path);
  }

  @override
  State<EngineDocHomePage> createState() => _EngineDocHomePageState();
}

class _EngineDocHomePageState extends State<EngineDocHomePage> {
  final _searchController = TextEditingController();
  String? _selectedPath;
  AnalysisResult? _analysis;
  StoredResult? _criticalAnalysis;
  StoredResult? _documentation;
  DocumentView _activeView = DocumentView.xray;
  bool _analyzing = false;
  bool _generatingAi = false;
  String? _error;
  String _search = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _chooseProject() async {
    final path = await widget.directoryPicker();
    if (!mounted || path == null) return;
    setState(() {
      _selectedPath = path;
      _analysis = null;
      _criticalAnalysis = null;
      _documentation = null;
      _activeView = DocumentView.xray;
      _error = null;
      _clearSearch();
    });
  }

  Future<void> _analyze() async {
    final path = _selectedPath;
    if (path == null) return;
    setState(() {
      _analyzing = true;
      _error = null;
    });
    try {
      final analysis = await widget.api.analyzeProject(path);
      ExistingResults existing = const ExistingResults();
      try {
        existing = await widget.api.existingResults(analysis.xrayPath);
      } on EngineDocApiException {
        // Optional old AI artifacts must not invalidate a fresh X-ray.
      }
      if (!mounted) return;
      setState(() {
        _analysis = analysis;
        _criticalAnalysis = existing.criticalAnalysis;
        _documentation = existing.documentation;
        _activeView = DocumentView.xray;
        _analyzing = false;
        _clearSearch();
      });
    } on EngineDocApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _analyzing = false;
        _error = error.message;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _analyzing = false;
        _error = 'Não foi possível concluir a análise. Tente novamente.';
      });
    }
  }

  Future<void> _generateAi() async {
    final analysis = _analysis;
    if (analysis == null) return;
    final request = await showDialog<AiGenerationRequest>(
      context: context,
      barrierDismissible: false,
      builder: (_) =>
          AiGenerationDialog(api: widget.api, xrayPath: analysis.xrayPath),
    );
    if (!mounted || request == null) return;
    setState(() {
      _generatingAi = true;
      _error = null;
    });
    try {
      final result = await widget.api.generateAi(request);
      if (!mounted) return;
      final stored = StoredResult(
        outputPath: result.outputPath,
        content: result.content,
      );
      setState(() {
        if (result.type == 'critical_analysis') {
          _criticalAnalysis = stored;
          _activeView = DocumentView.criticalAnalysis;
        } else {
          _documentation = stored;
          _activeView = DocumentView.documentation;
        }
        _generatingAi = false;
        _clearSearch();
      });
    } on EngineDocApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _generatingAi = false;
        _error = error.message;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _generatingAi = false;
        _error = 'Não foi possível concluir a geração com IA. Tente novamente.';
      });
    }
  }

  void _clearSearch() {
    _searchController.clear();
    _search = '';
  }

  String get _content => switch (_activeView) {
    DocumentView.xray => _analysis?.content ?? '',
    DocumentView.criticalAnalysis => _criticalAnalysis?.content ?? '',
    DocumentView.documentation => _documentation?.content ?? '',
  };

  String? get _activeFile => switch (_activeView) {
    DocumentView.xray => _analysis?.xrayPath,
    DocumentView.criticalAnalysis => _criticalAnalysis?.outputPath,
    DocumentView.documentation => _documentation?.outputPath,
  };

  int get _matchCount {
    if (_search.isEmpty) return 0;
    return RegExp(
      RegExp.escape(_search),
      caseSensitive: false,
    ).allMatches(_content).length;
  }

  Future<void> _openPath(String? path) async {
    if (path == null) return;
    try {
      await widget.pathOpener(path);
    } on Object {
      if (!mounted) return;
      setState(() => _error = 'Não foi possível abrir o caminho solicitado.');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 74,
        titleSpacing: 28,
        title: Row(
          children: [
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                color: const Color(0xFFF2C811),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                Icons.account_tree_outlined,
                color: Color(0xFF14233B),
              ),
            ),
            const SizedBox(width: 13),
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('ENGINE DOC POWER BI'),
                Text(
                  'Entenda, documente e revise projetos PBIP.',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w400),
                ),
              ],
            ),
          ],
        ),
        actions: const [
          Padding(
            padding: EdgeInsets.only(right: 28),
            child: Row(
              children: [
                Icon(Icons.computer_outlined, size: 18),
                SizedBox(width: 7),
                Text('Aplicação local'),
              ],
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(28, 24, 28, 28),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1440),
              child: Column(
                children: [
                  if (_error != null) ...[
                    _ErrorBanner(
                      message: _error!,
                      onDismiss: () => setState(() => _error = null),
                    ),
                    const SizedBox(height: 16),
                  ],
                  Expanded(
                    child: _analysis == null
                        ? _buildProjectSelection()
                        : _buildResult(),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildProjectSelection() {
    return Center(
      child: SingleChildScrollView(
        child: Container(
          width: 760,
          padding: const EdgeInsets.all(44),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            border: Border.all(
              color: Theme.of(context).colorScheme.outlineVariant,
            ),
            borderRadius: BorderRadius.circular(20),
            boxShadow: const [
              BoxShadow(
                color: Color(0x0A000000),
                blurRadius: 30,
                offset: Offset(0, 10),
              ),
            ],
          ),
          child: Column(
            children: [
              Container(
                width: 76,
                height: 76,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.folder_open_outlined, size: 36),
              ),
              const SizedBox(height: 24),
              Text(
                'Selecione seu projeto',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                'Escolha a pasta que contém o projeto PBIP. A validação e todo o processamento serão realizados pelo core Python.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 30),
              if (_selectedPath != null) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surfaceContainerLowest,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: Theme.of(context).colorScheme.outlineVariant,
                    ),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.check_circle_outline,
                        color: Color(0xFF237A57),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Projeto selecionado',
                              style: TextStyle(fontWeight: FontWeight.w600),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              _selectedPath!,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
              ],
              Wrap(
                spacing: 12,
                runSpacing: 12,
                alignment: WrapAlignment.center,
                children: [
                  OutlinedButton.icon(
                    onPressed: _analyzing ? null : _chooseProject,
                    icon: const Icon(Icons.folder_outlined),
                    label: Text(
                      _selectedPath == null
                          ? 'Selecionar pasta'
                          : 'Trocar pasta',
                    ),
                  ),
                  if (_selectedPath != null)
                    FilledButton.icon(
                      key: const Key('analyze-button'),
                      onPressed: _analyzing ? null : _analyze,
                      icon: _analyzing
                          ? const SizedBox.square(
                              dimension: 17,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.play_arrow_rounded),
                      label: Text(
                        _analyzing
                            ? 'Analisando projeto...'
                            : 'Analisar projeto',
                      ),
                    ),
                ],
              ),
              if (_analyzing) ...[
                const SizedBox(height: 24),
                const LinearProgressIndicator(),
                const SizedBox(height: 10),
                const Text('Analisando projeto...'),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildResult() {
    final analysis = _analysis!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    analysis.projectName,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 3),
                  Text(analysis.projectPath, overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
            TextButton.icon(
              onPressed: _generatingAi ? null : _chooseProject,
              icon: const Icon(Icons.swap_horiz),
              label: const Text('Trocar projeto'),
            ),
          ],
        ),
        if (analysis.warnings.isNotEmpty) ...[
          const SizedBox(height: 12),
          MaterialBanner(
            content: Text(
              'Análise concluída com ${analysis.warnings.length} aviso(s). Consulte a seção AVISOS do raio-X.',
            ),
            leading: const Icon(Icons.warning_amber_rounded),
            actions: const [SizedBox.shrink()],
          ),
        ],
        const SizedBox(height: 18),
        Row(
          children: [
            _DocumentTab(
              label: 'Raio-X',
              icon: Icons.manage_search_outlined,
              selected: _activeView == DocumentView.xray,
              onPressed: () => setState(() {
                _activeView = DocumentView.xray;
                _clearSearch();
              }),
            ),
            const SizedBox(width: 8),
            _DocumentTab(
              label: 'Análise crítica',
              icon: Icons.fact_check_outlined,
              selected: _activeView == DocumentView.criticalAnalysis,
              onPressed: _criticalAnalysis == null
                  ? null
                  : () => setState(() {
                      _activeView = DocumentView.criticalAnalysis;
                      _clearSearch();
                    }),
            ),
            const SizedBox(width: 8),
            _DocumentTab(
              label: 'Documentação',
              icon: Icons.description_outlined,
              selected: _activeView == DocumentView.documentation,
              onPressed: _documentation == null
                  ? null
                  : () => setState(() {
                      _activeView = DocumentView.documentation;
                      _clearSearch();
                    }),
            ),
            const Spacer(),
            FilledButton.icon(
              key: const Key('generate-ai-button'),
              onPressed: _generatingAi ? null : _generateAi,
              icon: _generatingAi
                  ? const SizedBox.square(
                      dimension: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.auto_awesome_outlined),
              label: Text(_generatingAi ? 'Gerando com IA...' : 'Gerar com IA'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              border: Border.all(
                color: Theme.of(context).colorScheme.outlineVariant,
              ),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(14),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          key: const Key('document-search'),
                          controller: _searchController,
                          onChanged: (value) => setState(() => _search = value),
                          decoration: InputDecoration(
                            hintText: 'Buscar no documento...',
                            prefixIcon: const Icon(Icons.search),
                            suffixIcon: _search.isEmpty
                                ? null
                                : IconButton(
                                    tooltip: 'Limpar busca',
                                    onPressed: () => setState(_clearSearch),
                                    icon: const Icon(Icons.close),
                                  ),
                          ),
                        ),
                      ),
                      if (_search.isNotEmpty) ...[
                        const SizedBox(width: 12),
                        Text('$_matchCount ocorrência(s)'),
                      ],
                    ],
                  ),
                ),
                const Divider(height: 1),
                Expanded(
                  child: Scrollbar(
                    thumbVisibility: true,
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(22),
                      child: SizedBox(
                        width: double.infinity,
                        child: SelectableText.rich(
                          _highlightedContent(context),
                          key: const Key('document-content'),
                        ),
                      ),
                    ),
                  ),
                ),
                const Divider(height: 1),
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      OutlinedButton.icon(
                        onPressed: () => _openPath(_activeFile),
                        icon: const Icon(Icons.open_in_new, size: 18),
                        label: const Text('Abrir arquivo'),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton.icon(
                        onPressed: () => _openPath(analysis.outputDir),
                        icon: const Icon(Icons.folder_open_outlined, size: 18),
                        label: const Text('Abrir pasta de saída'),
                      ),
                      const SizedBox(width: 8),
                      TextButton.icon(
                        onPressed: () async {
                          await Clipboard.setData(
                            ClipboardData(text: _content),
                          );
                          if (!mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Conteúdo copiado.')),
                          );
                        },
                        icon: const Icon(Icons.copy_outlined, size: 18),
                        label: const Text('Copiar conteúdo'),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  TextSpan _highlightedContent(BuildContext context) {
    const baseStyle = TextStyle(
      fontFamily: 'Consolas',
      fontSize: 13.5,
      height: 1.55,
      color: Color(0xFF263448),
    );
    if (_search.isEmpty) return TextSpan(text: _content, style: baseStyle);
    final matches = RegExp(
      RegExp.escape(_search),
      caseSensitive: false,
    ).allMatches(_content).toList();
    if (matches.isEmpty) return TextSpan(text: _content, style: baseStyle);
    final spans = <TextSpan>[];
    var offset = 0;
    for (final match in matches) {
      if (match.start > offset) {
        spans.add(TextSpan(text: _content.substring(offset, match.start)));
      }
      spans.add(
        TextSpan(
          text: _content.substring(match.start, match.end),
          style: const TextStyle(
            backgroundColor: Color(0xFFFFE47A),
            color: Color(0xFF14233B),
            fontWeight: FontWeight.w700,
          ),
        ),
      );
      offset = match.end;
    }
    if (offset < _content.length) {
      spans.add(TextSpan(text: _content.substring(offset)));
    }
    return TextSpan(style: baseStyle, children: spans);
  }
}

class _DocumentTab extends StatelessWidget {
  const _DocumentTab({
    required this.label,
    required this.icon,
    required this.selected,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) => selected
      ? FilledButton.tonalIcon(
          onPressed: onPressed,
          icon: Icon(icon),
          label: Text(label),
        )
      : TextButton.icon(
          onPressed: onPressed,
          icon: Icon(icon),
          label: Text(label),
        );
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message, required this.onDismiss});

  final String message;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 11, 8, 11),
      decoration: BoxDecoration(
        color: colors.errorContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, color: colors.onErrorContainer),
          const SizedBox(width: 10),
          Expanded(child: Text(message)),
          IconButton(
            onPressed: onDismiss,
            icon: const Icon(Icons.close),
            tooltip: 'Fechar',
          ),
        ],
      ),
    );
  }
}
