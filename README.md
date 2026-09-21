# Engine Doc Power BI

**PBIP → análise automática → documentação técnica**

Engine Doc Power BI é uma ferramenta CLI open source que lê projetos Power BI no formato PBIP e gera um raio-X técnico local do modelo sem banco, API própria ou interface gráfica. A extração é sempre determinística; opcionalmente, seu TXT final pode receber uma segunda camada de análise pela NVIDIA NIM.

## Início rápido

Requisito: Python 3.11 ou mais recente no Windows.

1. Coloque cada projeto PBIP em sua própria pasta dentro de `input/`.
2. Execute o serviço completo com análise por IA:

```powershell
.\start
```

3. Aguarde a geração do raio-X e, se desejar a revisão por IA, informe sua NVIDIA API Key quando solicitada.
4. Acesse <http://127.0.0.1:8765>.

O comando instala `requests` apenas se necessário, analisa os projetos, solicita a NVIDIA API Key, grava a documentação em `output/` e inicia a prévia local. A porta é fixa em **8765**. Se ela estiver ocupada, o script encerra o processo que a está escutando antes de iniciar o Engine Doc Power BI. Use `Ctrl+C` para parar.

### Comandos rápidos

```powershell
.\start   # serviço completo com análise por IA
.\local   # serviço completo sem IA; nenhuma informação é enviada
```

O comando anterior `\.\run.cmd` permanece disponível como alias de `\.\start`.

## O que é extraído

- tabelas, colunas físicas e colunas calculadas;
- medidas, expressões DAX, pastas de exibição e formatos;
- partições e expressões Power Query/M;
- relacionamentos, cardinalidade, direção de filtro e estado ativo;
- dependências entre medidas, colunas e relacionamentos;
- lineage em Mermaid;
- páginas, quantidade e tipos de visuais do relatório;
- nível de compatibilidade, cultura e avisos de leitura.

O leitor suporta definições semânticas TMDL e `model.bim`, além de relatórios PBIR e o formato legado `report.json`.

## Saída

Para cada projeto é criada uma pasta com:

```text
output/Nome-do-projeto/
├── Nome-do-projeto_raio_x.txt             # raio-X determinístico completo
├── Nome-do-projeto_raio_x_analise_ia.txt  # revisão opcional da NVIDIA
├── README.md                              # visão geral e inventário
├── dependencies.md                        # dependências e diagrama Mermaid
├── lineage.mmd                            # fonte Mermaid isolada
├── metadata.json                          # metadados para automação
└── tables/                                # documentação detalhada por tabela
```

Os arquivos de `input/` e `output/` são ignorados pelo Git porque projetos reais podem conter metadados sensíveis.

### Vários projetos e pastas previsíveis

O Engine Doc procura projetos recursivamente e espelha no `output/` a pasta em que cada projeto foi colocado. O nome interno do arquivo `.pbip` não altera esse caminho:

```text
input/
├── projeto1/
│   ├── RelatorioVendas.pbip
│   ├── RelatorioVendas.Report/
│   └── RelatorioVendas.SemanticModel/
└── projeto2/
    ├── RelatorioVendas.pbip
    ├── RelatorioVendas.Report/
    └── RelatorioVendas.SemanticModel/

output/
├── projeto1/
│   ├── RelatorioVendas_raio_x.txt
│   └── RelatorioVendas_raio_x_analise_ia.txt
└── projeto2/
    ├── RelatorioVendas_raio_x.txt
    └── RelatorioVendas_raio_x_analise_ia.txt
```

Assim, projetos com o mesmo nome interno continuam isolados. Se uma única pasta contiver mais de um descritor `.pbip`, o Engine Doc cria uma subpasta com o nome de cada projeto para impedir sobrescritas.

## Uso somente como CLI

Para gerar os arquivos e solicitar a análise por IA sem manter a prévia local ativa:

```powershell
python main.py
```

Para produzir somente o raio-X local e determinístico, sem solicitar chave nem enviar conteúdo externo:

```powershell
python main.py --skip-ai
```

Outras opções:

```powershell
python main.py --help
python main.py --input C:\caminho\pbip --output C:\caminho\docs
python main.py --serve --port 8765
```

Após instalar o pacote com `pip install -e .`, o comando `engine-doc-power-bi` também fica disponível.

## Análise técnica com IA

Depois que o Engine Doc Power BI conclui a extração e grava o arquivo `*_raio_x.txt`, ele pode enviar **somente o conteúdo desse TXT** ao modelo `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`, hospedado pela NVIDIA NIM. O PBIP e seus arquivos internos nunca são enviados ou abertos pela camada de IA.

O modelo pode sugerir melhorias relacionadas a:

- DAX;
- relacionamentos e modelagem;
- performance;
- dependências;
- organização e manutenção.

Para utilizar a funcionalidade, é necessário possuir uma NVIDIA API Key. A chave é solicitada diretamente no terminal com entrada oculta, mantida somente em memória durante a execução e não é gravada em arquivos, `.env`, configurações ou logs.

Antes da solicitação da chave, o terminal informa claramente que o TXT será enviado à NVIDIA. Se a chave estiver vazia, a autenticação falhar, houver limite de requisições, timeout, falha de conexão ou resposta inválida, somente a etapa de IA é encerrada; o raio-X já produzido permanece preservado.

Importante:

- o conteúdo do TXT representa metadados do projeto e será enviado à API NVIDIA NIM quando a análise for aceita;
- a análise por IA não substitui validação técnica;
- nenhuma API Key deve ser adicionada ao código-fonte;
- o raio-X é produzido independentemente da IA;
- use `--skip-ai` quando nenhuma informação puder sair do ambiente local.

## Testes

```powershell
python -m unittest discover -s tests -v
```

## Limites conhecidos

A extração de dependências DAX é deliberadamente conservadora e baseada em referências explícitas. Referências dinâmicas, alguns recursos novos do Power BI e expressões que dependem de resolução semântica completa podem não aparecer no lineage. Arquivos inválidos não interrompem os demais projetos: o problema é incluído na seção de avisos.

## Estrutura

```text
engine_doc_power_bi/
├── input/
├── output/
├── scripts/
│   └── run.ps1
├── src/engine_doc/
│   ├── analysis/
│   ├── exporters/
│   ├── parsers/
│   ├── cli.py
│   ├── discovery.py
│   └── models.py
├── tests/
├── main.py
├── run.cmd
├── pyproject.toml
└── requirements.txt
```

## Licença

[MIT](LICENSE)
