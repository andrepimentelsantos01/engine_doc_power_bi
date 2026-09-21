![Banner do Engine Doc Power BI](images/banner%5D.png)

# Engine Doc Power BI

Engine Doc Power BI é uma ferramenta local em Python para analisar projetos
Power BI no formato PBIP.

Ela lê os artefatos locais do projeto e gera um raio-X técnico em TXT. A
análise principal não precisa de banco, servidor ou inteligência artificial.

## O que ele faz

O Engine Doc transforma a estrutura de um projeto PBIP em documentação técnica
pesquisável. O resultado mostra como o modelo semântico e o relatório estão
organizados, quais objetos dependem uns dos outros e o impacto provável de uma
alteração.

Cada pasta colocada em `input/` é processada separadamente. A estrutura
equivalente é preservada em `output/`, evitando conflitos entre projetos.

## O que é analisado

- fontes e partições;
- tabelas e colunas;
- colunas calculadas;
- medidas e expressões DAX;
- relacionamentos e direção de filtro;
- dependências entre objetos;
- páginas e visuais;
- campos e filtros usados pelos visuais;
- lineage;
- análise de impacto;
- avisos sobre partes que não puderam ser interpretadas.

São aceitos modelos semânticos TMDL e `model.bim`, além de relatórios PBIR e
relatórios legados em `report.json`.

## Como funciona

```text
Projeto PBIP
    ↓
Engine Doc Power BI
    ↓
Raio-X técnico em TXT
    ↓
Análise opcional com IA
```

## Instalação

Requisitos:

- Python 3.11 ou mais recente;
- Windows para os atalhos `start` e `local`.

```powershell
git clone https://github.com/andrepimentelsantos01/engine_doc_power_bi.git
cd engine_doc_power_bi
python -m pip install -r requirements.txt
```

O projeto possui somente uma dependência de execução: `requests`, usada pelas
integrações opcionais com IA.

## Uso

Coloque cada projeto em sua própria pasta:

```text
input/
├── projeto_financeiro/
│   ├── Financeiro.pbip
│   ├── Financeiro.Report/
│   └── Financeiro.SemanticModel/
└── projeto_comercial/
    ├── Comercial.pbip
    ├── Comercial.Report/
    └── Comercial.SemanticModel/
```

Para gerar o raio-X e escolher se deseja usar IA:

```powershell
python main.py
```

Para executar somente a análise local:

```powershell
python main.py --skip-ai
```

Para informar outras pastas:

```powershell
python main.py --input C:\caminho\pbip --output C:\caminho\documentacao --skip-ai
```

### Atalhos no Windows

```powershell
.\start   # CLI: análise, IA opcional e prévia local
.\local   # CLI: análise local, sem IA
.\app     # aplicação local: backend + Flutter Web no navegador
```

Os atalhos usam a porta fixa `8765`. Se ela estiver ocupada, o processo que a
estiver escutando será encerrado antes da inicialização. Use `Ctrl+C` para
fechar a prévia.

## Exemplo

O repositório inclui o projeto de demonstração `projeto_dashboard_ecomerce`.
Ele não fica em `input/` para evitar processamento automático.

Execute diretamente:

```powershell
python main.py --input examples --output output-demo --skip-ai
```

O raio-X será criado em:

```text
output-demo/projetodashBI/projeto_dashboard_ecomerce_raio_x.txt
```

## Saída

Cada projeto recebe uma pasta própria:

```text
output/projeto_financeiro/
├── Financeiro_raio_x.txt
├── Financeiro_raio_x_analise_ia.txt  # análise crítica opcional
├── Financeiro_documentacao_ia.txt    # documentação opcional
├── README.md
├── dependencies.md
├── lineage.mmd
├── metadata.json
└── tables/
```

Trecho do TXT:

```text
TABELA: Vendas

MEDIDA: Vendas[Faturamento Total]
Expressão DAX:
SUMX(Vendas, Vendas[Quantidade] * Vendas[Preco Unitario])

DEPENDE DE:
- Coluna: Vendas[Quantidade]
- Coluna: Vendas[Preco Unitario]

USADA POR / DEPENDÊNCIAS A JUSANTE:
- Visual: Resumo/GraficoFaturamento
```

Projetos e documentos gerados podem conter metadados sensíveis. Por isso,
`input/` e `output/` são ignorados pelo Git.

## Análise com IA

A IA é opcional e só é oferecida depois da criação de todos os raios-X.
Primeiro, escolha o tipo de entrega:

```text
[1] Análise crítica
[2] Documentação executiva/técnica
[0] Finalizar sem IA
```

A análise crítica avalia evidências, dependências e pontos que merecem
atenção. A documentação descreve arquitetura, fontes, modelo, medidas,
páginas, visuais e lineage sem atuar como auditoria. As duas opções usam
somente o TXT final do raio-X.

Depois, escolha o provedor:

```text
[1] NVIDIA NIM
[2] OpenRouter
[0] Voltar
```

Na NVIDIA NIM, o modelo configurado é exibido antes da análise.

No OpenRouter, o catálogo oficial é consultado dinamicamente. Somente modelos
de texto com preços confirmados como zero são apresentados. A opção automática
usa `openrouter/free`. A gratuidade é validada novamente antes de cada envio.
Se ela não puder ser confirmada, nenhuma análise é solicitada.

Uma falha de IA não apaga nem invalida o raio-X local, a análise crítica
existente ou a documentação gerada anteriormente.

## Privacidade

O processamento PBIP é local. Nenhum arquivo é enviado durante a geração do
raio-X.

Ao escolher IA, somente o conteúdo do TXT é enviado:

- diretamente à NVIDIA NIM; ou
- ao OpenRouter e ao provedor responsável pelo modelo selecionado.

As API Keys são solicitadas com entrada oculta, permanecem somente em memória
e não são gravadas em arquivos, configurações, relatórios ou logs.

Use `--skip-ai` quando nenhuma informação puder sair do computador.

## Interface Flutter Desktop

O mesmo Engine Doc pode ser usado pelo CLI ou pela interface Flutter para
Windows. O frontend é apenas a camada de apresentação: parsing PBIP/TMDL,
análises, exporters, prompts e providers de IA continuam no core Python.

```text
Flutter Desktop
      ↓ JSON em 127.0.0.1:8766
API local Python
      ↓
Engine Doc Core → PBIP / Raio-X / IA
```

Durante o desenvolvimento, inicie os dois processos em terminais separados:

```powershell
# Terminal 1 — raiz do repositório
python desktop_backend.py

# Terminal 2 (desenvolvimento)
cd frontend
flutter run -d chrome
```

Na interface, selecione a pasta do projeto pelo Explorer, gere o raio-X e,
opcionalmente, escolha análise crítica ou documentação por NVIDIA NIM ou
OpenRouter. Os modelos gratuitos do OpenRouter são consultados pelo backend.
Os resultados TXT são gravados em `output/` e podem ser abertos pelo app.

A API local escuta somente em `127.0.0.1`. A API Key é enviada apenas na
requisição da operação de IA, permanece em memória e não é persistida nem
registrada em logs. Os arquivos PBIP não são enviados aos providers.

Para validar o frontend:

```powershell
cd frontend
flutter analyze
flutter test
flutter build windows --debug
```
## Limitações

- O parser cobre os formatos PBIP, TMDL e PBIR conhecidos pelo projeto. Novas
  versões do Power BI podem introduzir estruturas ainda não reconhecidas.
- A análise de dependências DAX é conservadora e baseada em referências
  explícitas. Expressões dinâmicas podem não aparecer no lineage.
- Ausência de uso direto em visual não prova que um objeto seja inútil.
- O projeto de exemplo é uma fixture artificial e não substitui a validação de
  um projeto salvo pelo Power BI Desktop.
- A revisão por IA é consultiva e deve ser validada tecnicamente.

## Testes

```powershell
python -m unittest discover -s tests -v
```

Os testes de IA usam mocks e não realizam chamadas reais aos provedores.

## Contribuindo

Contribuições são bem-vindas. Antes de enviar uma alteração, execute a suíte de
testes e não inclua projetos PBIP reais, dados sensíveis ou API Keys.

## Licença

[MIT](LICENSE)
