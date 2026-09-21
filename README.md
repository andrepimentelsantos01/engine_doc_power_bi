# Engine Doc Power BI

**PBIP → análise automática → documentação técnica**

Engine Doc Power BI é uma ferramenta CLI open source que lê projetos Power BI no formato PBIP e gera um raio-x técnico local do modelo sem banco, API, interface gráfica ou IA.

## Início rápido

Requisito: Python 3.11 ou mais recente no Windows.

1. Coloque um ou mais projetos PBIP dentro de `input/`.
2. Execute:

```powershell
.\run.cmd
```

3. Acesse <http://127.0.0.1:8765>.

O comando analisa os projetos, grava a documentação em `output/` e inicia a prévia local. A porta é fixa em **8765**. Se ela estiver ocupada, o script encerra o processo que a está escutando antes de iniciar o Engine Doc Power BI. Use `Ctrl+C` para parar.

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
├── README.md          # visão geral e inventário
├── dependencies.md    # dependências e diagrama Mermaid
├── lineage.mmd        # fonte Mermaid isolada
├── metadata.json      # metadados para automação
└── tables/            # documentação detalhada por tabela
```

Os arquivos de `input/` e `output/` são ignorados pelo Git porque projetos reais podem conter metadados sensíveis.

## Uso somente como CLI

Para gerar os arquivos sem manter a prévia local ativa:

```powershell
python main.py
```

Outras opções:

```powershell
python main.py --help
python main.py --input C:\caminho\pbip --output C:\caminho\docs
python main.py --serve --port 8765
```

Após instalar o pacote com `pip install -e .`, o comando `engine-doc-power-bi` também fica disponível.

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

