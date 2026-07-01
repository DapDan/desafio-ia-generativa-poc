# POC — Extração de Dados de Documentos com IA Generativa

Prova de Conceito (Entregável 2) do Desafio Técnico — Pesquisador(a) em IA Generativa (P&D).
**Candidato:** Danilo &nbsp;|&nbsp; **Data:** 28 de junho de 2026

Este repositório acompanha o **Dossiê de Pesquisa** (Entregável 1, PDF) e demonstra a técnica ali
recomendada: **extração multimodal de documentos em passo único, com Structured Outputs**, em
substituição ao pipeline atual de duas chamadas (interpretação/extração + formatação).

👉 **Comece por `notebooks/POC.ipynb`** — reúne os dois scripts abaixo com narrativa e outputs já
executados.

## Estrutura

```
poc/
├── schemas/                        JSON Schemas dos 3 casos de uso do desafio
├── samples/                        Os 3 documentos de exemplo fornecidos no desafio
├── src/
│   ├── extrator_single_pass.py     Técnica A (recomendada) — 1 chamada, visão nativa + Structured
│   │                                Outputs via Claude API. Requer ANTHROPIC_API_KEY.
│   └── baseline_ocr_local.py       Baseline 100% local (Tesseract OCR) — roda sem nenhuma chave de
│                                    API. Gerou os resultados empíricos da Seção 4.6 do Dossiê.
├── outputs/                        Resultados salvos em JSON
├── notebooks/POC.ipynb             Notebook consolidado, já executado
└── requirements.txt
```

## Nota importante — o que roda neste ambiente vs. o que precisa de uma credencial

O ambiente usado para desenvolver este desafio **não tem GPU e não tem uma `ANTHROPIC_API_KEY`
configurada** (nem de nenhum outro provedor de LLM). Por isso:

- **`src/extrator_single_pass.py`** (a técnica recomendada no Dossiê) está **implementado
  corretamente e pronto para produção** — monta o payload multimodal, codifica o documento,
  define o schema estrito (`strict: true`) e faz a chamada real à Claude API. Sem uma chave, a
  chamada falha *apenas* na etapa de autenticação (comportamento testado e confirmado — ver
  notebook). Para rodar de ponta a ponta:

  ```bash
  export ANTHROPIC_API_KEY="sk-ant-..."
  python src/extrator_single_pass.py
  ```

- **`src/baseline_ocr_local.py`** roda de ponta a ponta neste ambiente, sem nenhuma credencial,
  usando apenas Tesseract (OCR open-source). Foi a alternativa que pôde de fato ser testada e
  executada localmente — conforme previsto na "Nota Importante sobre a POC" do próprio enunciado
  do desafio — e serve de baseline empírico para os achados da Seção 4.6 do Dossiê (limitações de
  um pipeline OCR-primeiro nos 3 documentos de teste: CNH, fatura de energia e o paper "The Claude
  3 Model Family").

## Como rodar

### Dependências de sistema (para o baseline OCR)
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-por poppler-utils
```

### Dependências Python
```bash
pip install -r requirements.txt
```

### Baseline local (roda sem nenhuma configuração adicional)
```bash
cd poc
python src/baseline_ocr_local.py
```

### Técnica recomendada (requer chave de API)
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
cd poc
python src/extrator_single_pass.py
```

### Notebook completo
```bash
cd poc/notebooks
jupyter notebook POC.ipynb
```

## Os 3 casos de uso do desafio

| Caso | Documento | Schema | Objetivo |
|---|---|---|---|
| 1 | `samples/cnh_exemplo.jpeg` | `schemas/schema_cnh.json` | Extrair campos estruturados (nome, CPF, datas, filiação) |
| 2 | `samples/claude3_model_family.pdf` | `schemas/schema_documento_extenso.json` | Preservar layout de tabelas + interpretar gráficos |
| 3 | `samples/fatura_energia.jpg` | `schemas/schema_fatura.json` | Extrair fatura preservando organização das seções |

## Ver também

O documento técnico completo (`Dossie_Pesquisa_IA_Generativa.pdf`) traz a metodologia de pesquisa,
a comparação de 3 técnicas, as projeções de custo/latência, os resultados de benchmarks
independentes, os achados empíricos deste mesmo baseline, e a recomendação final com roadmap de
implantação.
