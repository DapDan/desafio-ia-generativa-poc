"""
extrator_single_pass.py
========================
Implementacao de referencia da arquitetura RECOMENDADA no Dossie de Pesquisa:

    Extracao multimodal em passo unico (VLM nativo) + Structured Outputs

Em vez do pipeline atual (2 completions: (1) interpretacao/extracao com um LLM
"le" o documento e (2) uma segunda chamada formata o resultado no JSON exigido
pelo cliente), aqui uma UNICA chamada ao modelo ja recebe o documento (imagem
ou PDF nativo) e um JSON Schema estrito via "structured outputs" (tool use com
strict:true). O modelo "ve" o documento e devolve diretamente um objeto que
JA satisfaz o schema do cliente -- eliminando a segunda chamada por completo.

Isso ataca directamente os 4 problemas descritos no desafio:
  - Latencia:      1 round-trip em vez de 2.
  - Custo:         menos tokens totais + possibilidade de usar um modelo menor
                    (ex.: Haiku) ja que a tarefa por chamada fica mais simples.
  - Complexidade:  o PDF e enviado nativamente (ate 100 paginas / 32MB por
                    requisicao), sem precisar de OCR/rasterizacao externa.
  - Graficos/imagens: o modelo e multimodal (visao nativa), entao interpreta
                    graficos e nao apenas texto (o pipeline OCR-first perde
                    essa informacao).

Requer a variavel de ambiente ANTHROPIC_API_KEY para efetivamente chamar a
API. Sem uma chave configurada, as funcoes deste modulo continuam
import-aveis e testaveis (schemas, montagem do payload, etc.), mas a
chamada de rede falha com uma mensagem clara -- ver notebooks/POC.ipynb
para a explicacao completa dessa limitacao neste ambiente de execucao.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import anthropic

# Modelo recomendado para extracao de documentos: familia Haiku/Sonnet, que o
# benchmark independente IDP Leaderboard (Nanonets, mar/2026) mostra ficar
# estatisticamente empatada com os modelos "topo de linha" em tarefas de
# EXTRACAO (texto, tabela, formula, layout) -- a diferenca de acuracia entre
# tiers so aparece em tarefas de raciocinio aberto, nao em extracao. Ver
# Secao 4 do Dossie para a citacao completa.
MODELO_PADRAO = "claude-haiku-4-5"


@dataclass
class ResultadoExtracao:
    caso: str
    modelo: str
    ok: bool
    dados: Optional[dict[str, Any]]
    erro: Optional[str]
    latencia_segundos: Optional[float]
    tokens_entrada: Optional[int]
    tokens_saida: Optional[int]


def _carregar_schema(caminho_schema: str | Path) -> dict[str, Any]:
    with open(caminho_schema, "r", encoding="utf-8") as f:
        return json.load(f)


def _codificar_arquivo_base64(caminho_arquivo: str | Path) -> tuple[str, str]:
    caminho_arquivo = Path(caminho_arquivo)
    media_type, _ = mimetypes.guess_type(str(caminho_arquivo))
    if media_type is None:
        media_type = "application/octet-stream"
    with open(caminho_arquivo, "rb") as f:
        dados_b64 = base64.standard_b64encode(f.read()).decode("utf-8")
    return dados_b64, media_type


def _montar_bloco_documento(caminho_arquivo: str | Path) -> dict[str, Any]:
    """Monta o content-block de imagem ou PDF nativo para a Messages API."""
    dados_b64, media_type = _codificar_arquivo_base64(caminho_arquivo)
    tipo_bloco = "document" if media_type == "application/pdf" else "image"
    return {
        "type": tipo_bloco,
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": dados_b64,
        },
    }


def extrair_documento(
    caminho_arquivo: str | Path,
    caminho_schema: str | Path,
    instrucao: str,
    caso: str = "documento",
    modelo: str = MODELO_PADRAO,
    cliente: Optional[anthropic.Anthropic] = None,
    max_tokens: int = 4096,
) -> ResultadoExtracao:
    """
    Executa a extracao em PASSO UNICO: envia o documento (imagem/PDF) +
    instrucao + JSON Schema estrito em uma unica chamada 'messages.create',
    usando tool use com strict=True para GARANTIR que a resposta segue
    exatamente o schema do cliente (ver docs: Structured Outputs).

    Retorna um ResultadoExtracao com dados/latencia/tokens ja preenchidos,
    ou com ok=False e 'erro' preenchido caso a chamada nao possa ser feita
    (ex.: ANTHROPIC_API_KEY ausente neste ambiente).
    """
    schema = _carregar_schema(caminho_schema)
    nome_ferramenta = schema["name"]

    if cliente is None:
        cliente = anthropic.Anthropic()  # le ANTHROPIC_API_KEY do ambiente

    bloco_documento = _montar_bloco_documento(caminho_arquivo)

    inicio = time.perf_counter()
    try:
        resposta = cliente.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            tools=[
                {
                    "name": schema["name"],
                    "description": schema["description"],
                    "input_schema": schema["input_schema"],
                    "strict": True,  # <-- Structured Outputs: schema garantido
                }
            ],
            tool_choice={"type": "tool", "name": nome_ferramenta},
            messages=[
                {
                    "role": "user",
                    "content": [
                        bloco_documento,
                        {"type": "text", "text": instrucao},
                    ],
                }
            ],
        )
    except Exception as exc:  # noqa: BLE001 - queremos capturar qualquer falha de rede/auth
        return ResultadoExtracao(
            caso=caso,
            modelo=modelo,
            ok=False,
            dados=None,
            erro=f"{type(exc).__name__}: {exc}",
            latencia_segundos=None,
            tokens_entrada=None,
            tokens_saida=None,
        )
    latencia = time.perf_counter() - inicio

    dados_extraidos = None
    for bloco in resposta.content:
        if bloco.type == "tool_use" and bloco.name == nome_ferramenta:
            dados_extraidos = bloco.input
            break

    return ResultadoExtracao(
        caso=caso,
        modelo=modelo,
        ok=dados_extraidos is not None,
        dados=dados_extraidos,
        erro=None if dados_extraidos is not None else "Modelo nao retornou tool_use esperado.",
        latencia_segundos=round(latencia, 3),
        tokens_entrada=resposta.usage.input_tokens,
        tokens_saida=resposta.usage.output_tokens,
    )


# ---------------------------------------------------------------------------
# Definicao dos 3 casos de uso exigidos pelo desafio, prontos para chamar.
# ---------------------------------------------------------------------------

CASOS = {
    "cnh": dict(
        caminho_arquivo="samples/cnh_exemplo.jpeg",
        caminho_schema="schemas/schema_cnh.json",
        instrucao=(
            "Este e um documento de identificacao brasileiro (CNH). Extraia os "
            "campos solicitados na ferramenta exatamente como aparecem "
            "impressos. Se algum campo estiver ilegivel, preencha com "
            "'ILEGIVEL' e reflita isso em confianca_extracao."
        ),
    ),
    "fatura": dict(
        caminho_arquivo="samples/fatura_energia.jpg",
        caminho_schema="schemas/schema_fatura.json",
        instrucao=(
            "Esta e uma fatura de energia eletrica brasileira. Extraia os "
            "dados solicitados na ferramenta. Preste atencao especial ao "
            "historico de consumo mensal (grafico de barras 'HISTORICO DE "
            "CONSUMO') e a tabela de tributos (ICMS/PIS/COFINS) -- ambos "
            "exigem interpretacao visual, nao apenas leitura de texto corrido."
        ),
    ),
    "documento_extenso": dict(
        caminho_arquivo="samples/claude3_model_family.pdf",
        caminho_schema="schemas/schema_documento_extenso.json",
        instrucao=(
            "Processe a PAGINA 8 deste documento (uma tabela densa de "
            "benchmarks multimodais). Devolva os blocos de conteudo "
            "preservando a tabela em Markdown com todas as linhas/colunas."
        ),
    ),
}


def executar_todos_os_casos(modelo: str = MODELO_PADRAO) -> list[ResultadoExtracao]:
    resultados = []
    for nome_caso, cfg in CASOS.items():
        resultado = extrair_documento(
            caminho_arquivo=cfg["caminho_arquivo"],
            caminho_schema=cfg["caminho_schema"],
            instrucao=cfg["instrucao"],
            caso=nome_caso,
            modelo=modelo,
        )
        resultados.append(resultado)
    return resultados


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "[AVISO] ANTHROPIC_API_KEY nao definida. Este script monta e "
            "tenta as chamadas reais; sem a chave, cada caso retornara "
            "ok=False com o erro de autenticacao (comportamento esperado "
            "neste sandbox). Defina a variavel de ambiente para reproduzir "
            "com uma conta real.\n"
        )
    for resultado in executar_todos_os_casos():
        print("=" * 70)
        print(f"Caso: {resultado.caso} | ok={resultado.ok} | latencia={resultado.latencia_segundos}s")
        if resultado.ok:
            print(json.dumps(resultado.dados, ensure_ascii=False, indent=2))
        else:
            print(f"Erro: {resultado.erro}")
