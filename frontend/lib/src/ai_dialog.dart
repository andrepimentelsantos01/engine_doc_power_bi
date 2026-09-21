import 'package:flutter/material.dart';

import 'api.dart';
import 'models.dart';

class AiGenerationDialog extends StatefulWidget {
  const AiGenerationDialog({
    required this.api,
    required this.xrayPath,
    super.key,
  });

  final EngineDocApi api;
  final String xrayPath;

  @override
  State<AiGenerationDialog> createState() => _AiGenerationDialogState();
}

class _AiGenerationDialogState extends State<AiGenerationDialog> {
  final _keyController = TextEditingController();
  int _step = 0;
  String _mode = 'critical_analysis';
  String _provider = 'nvidia';
  bool _obscureKey = true;
  bool _loadingModels = false;
  List<AiModel> _models = const [];
  String? _selectedModel;
  String? _error;

  @override
  void dispose() {
    _keyController.clear();
    _keyController.dispose();
    super.dispose();
  }

  String get _title => switch (_step) {
    0 => 'O que deseja gerar?',
    1 => 'Escolha o provedor de IA',
    2 => 'Credencial e modelo',
    _ => 'Confirmar geração',
  };

  Future<void> _continue() async {
    setState(() => _error = null);
    if (_step < 2) {
      setState(() => _step += 1);
      return;
    }
    if (_step == 2) {
      if (_keyController.text.trim().isEmpty) {
        setState(() => _error = 'Informe a API Key do provedor selecionado.');
        return;
      }
      if (_provider == 'openrouter' && _models.isEmpty) {
        setState(() => _loadingModels = true);
        try {
          final models = await widget.api.listOpenRouterModels(
            _keyController.text.trim(),
          );
          if (!mounted) return;
          if (models.isEmpty) {
            setState(() {
              _loadingModels = false;
              _error = 'Nenhum modelo gratuito compatível está disponível no momento.';
            });
            return;
          }
          setState(() {
            _models = models;
            _selectedModel = models.first.id;
            _loadingModels = false;
            _step = 3;
          });
        } on EngineDocApiException catch (error) {
          if (!mounted) return;
          setState(() {
            _loadingModels = false;
            _error = error.message;
          });
        } on Object {
          if (!mounted) return;
          setState(() {
            _loadingModels = false;
            _error = 'Não foi possível consultar os modelos. Tente novamente.';
          });
        }
        return;
      }
      setState(() => _step = 3);
      return;
    }

    final request = AiGenerationRequest(
      mode: _mode,
      provider: _provider,
      apiKey: _keyController.text.trim(),
      xrayPath: widget.xrayPath,
      model: _provider == 'openrouter' ? _selectedModel : null,
    );
    _keyController.clear();
    Navigator.of(context).pop(request);
  }

  void _back() {
    if (_step == 0) {
      Navigator.of(context).pop();
      return;
    }
    setState(() {
      _step -= 1;
      _error = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      insetPadding: const EdgeInsets.all(32),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 680, maxHeight: 680),
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 38,
                    height: 38,
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.primaryContainer,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.auto_awesome_outlined, size: 20),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _title,
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        Text(
                          'Etapa ${_step + 1} de 4',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Fechar',
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              LinearProgressIndicator(value: (_step + 1) / 4),
              const SizedBox(height: 24),
              Expanded(child: SingleChildScrollView(child: _stepContent())),
              if (_error != null) ...[
                const SizedBox(height: 12),
                _MessageBanner(message: _error!, isError: true),
              ],
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _loadingModels ? null : _back,
                    child: Text(_step == 0 ? 'Cancelar' : 'Voltar'),
                  ),
                  const SizedBox(width: 12),
                  FilledButton.icon(
                    onPressed: _loadingModels ? null : _continue,
                    icon: _loadingModels
                        ? const SizedBox.square(
                            dimension: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : Icon(
                            _step == 3
                                ? Icons.auto_awesome
                                : Icons.arrow_forward,
                          ),
                    label: Text(
                      _loadingModels
                          ? 'Consultando modelos...'
                          : _step == 3
                          ? 'Gerar'
                          : 'Continuar',
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _stepContent() => switch (_step) {
    0 => Column(
      children: [
        _ChoiceCard(
          selected: _mode == 'critical_analysis',
          title: 'Análise crítica',
          description: 'Revisa estrutura, dependências, modelagem e possíveis oportunidades de melhoria.',
          icon: Icons.fact_check_outlined,
          onTap: () => setState(() => _mode = 'critical_analysis'),
        ),
        const SizedBox(height: 12),
        _ChoiceCard(
          selected: _mode == 'documentation',
          title: 'Documentação executiva/técnica',
          description: 'Gera uma base para entendimento, manutenção e passagem de conhecimento.',
          icon: Icons.description_outlined,
          onTap: () => setState(() => _mode = 'documentation'),
        ),
      ],
    ),
    1 => Column(
      children: [
        _ChoiceCard(
          selected: _provider == 'nvidia',
          title: 'NVIDIA NIM',
          description: 'Usa o modelo NVIDIA configurado no Engine Doc.',
          icon: Icons.memory_outlined,
          onTap: () => setState(() {
            _provider = 'nvidia';
            _models = const [];
            _selectedModel = null;
          }),
        ),
        const SizedBox(height: 12),
        _ChoiceCard(
          selected: _provider == 'openrouter',
          title: 'OpenRouter',
          description: 'Consulta no backend apenas modelos de texto confirmados como gratuitos.',
          icon: Icons.hub_outlined,
          onTap: () => setState(() => _provider = 'openrouter'),
        ),
      ],
    ),
    2 => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          key: const Key('api-key-field'),
          controller: _keyController,
          obscureText: _obscureKey,
          enableSuggestions: false,
          autocorrect: false,
          decoration: InputDecoration(
            labelText: 'API Key',
            hintText: 'Informe a chave somente para esta execução',
            prefixIcon: const Icon(Icons.key_outlined),
            suffixIcon: IconButton(
              tooltip: _obscureKey ? 'Mostrar chave' : 'Ocultar chave',
              onPressed: () => setState(() => _obscureKey = !_obscureKey),
              icon: Icon(
                _obscureKey
                    ? Icons.visibility_outlined
                    : Icons.visibility_off_outlined,
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        const _MessageBanner(
          message: 'A chave fica somente em memória e não é salva em arquivos ou configurações.',
        ),
      ],
    ),
    _ => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SummaryRow(
          label: 'Gerar',
          value: _mode == 'critical_analysis'
              ? 'Análise crítica'
              : 'Documentação executiva/técnica',
        ),
        _SummaryRow(
          label: 'Provedor',
          value: _provider == 'nvidia' ? 'NVIDIA NIM' : 'OpenRouter',
        ),
        if (_provider == 'openrouter') ...[
          const SizedBox(height: 16),
          Text(
            'Modelo gratuito',
            style: Theme.of(context).textTheme.labelLarge,
          ),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            key: const Key('model-dropdown'),
            initialValue: _selectedModel,
            isExpanded: true,
            items: _models
                .map(
                  (model) => DropdownMenuItem(
                    value: model.id,
                    child: Text(
                      model.automatic
                          ? 'Seleção automática gratuita — ${model.name}'
                          : model.name,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                )
                .toList(),
            onChanged: (value) => setState(() => _selectedModel = value),
          ),
        ],
        const SizedBox(height: 20),
        _MessageBanner(
          message: _provider == 'openrouter'
              ? 'Somente o conteúdo do raio-X será enviado ao OpenRouter e ao provedor do modelo selecionado. Os arquivos PBIP não são enviados.'
              : 'Somente o conteúdo do raio-X será enviado à NVIDIA NIM. Os arquivos PBIP não são enviados.',
        ),
      ],
    ),
  };
}

class _ChoiceCard extends StatelessWidget {
  const _ChoiceCard({
    required this.selected,
    required this.title,
    required this.description,
    required this.icon,
    required this.onTap,
  });

  final bool selected;
  final String title;
  final String description;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 140),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: selected
              ? colors.primaryContainer.withValues(alpha: .45)
              : colors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected ? colors.primary : colors.outlineVariant,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              icon,
              color: selected ? colors.primary : colors.onSurfaceVariant,
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 4),
                  Text(description),
                ],
              ),
            ),
            Icon(
              selected ? Icons.radio_button_checked : Icons.radio_button_off,
              color: selected ? colors.primary : colors.onSurfaceVariant,
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 110,
          child: Text(label, style: Theme.of(context).textTheme.labelLarge),
        ),
        Expanded(child: Text(value)),
      ],
    ),
  );
}

class _MessageBanner extends StatelessWidget {
  const _MessageBanner({required this.message, this.isError = false});

  final String message;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isError ? colors.errorContainer : colors.secondaryContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            isError ? Icons.error_outline : Icons.privacy_tip_outlined,
            size: 19,
            color: isError
                ? colors.onErrorContainer
                : colors.onSecondaryContainer,
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(message)),
        ],
      ),
    );
  }
}
