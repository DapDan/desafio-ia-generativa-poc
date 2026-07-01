"""
baseline_ocr_local.py
======================
Baseline 100% LOCAL (sem chamadas de API), executavel neste sandbox sem GPU e
sem chaves de servico. Implementa o "primeiro estagio" tipico de um pipeline
OCR-first (Tesseract, motor open-source classico) para servir de contraponto
empirico ao pipeline multimodal recomendado no Dossie.

Por que este script existe:
Este ambiente de execucao nao tem GPU, tem 1 vCPU / ~4GB RAM, e NAO possui
uma ANTHROPIC_API_KEY (nem de qualquer outro provedor) configurada -- ou
seja, nenhuma chamada real a uma VLM comercial pode ser feita a partir daqui
(ver extrator_single_pass.py). Como o proprio enunciado do desafio permite
("sua POC pode implementar a melhor alternativa viavel que voce conseguiu
testar e executar"), este script roda de fato, nestas maquina, e produz
numeros REAIS (nao estimados) de tempo de processamento e qualidade de
extracao de texto puro via OCR classico -- uteis para ilustrar, com dados
proprios, as limitacoes discutidas no Dossie (perda de layout/tabelas,
ausencia de interpretacao de graficos, necessidade de uma 2a etapa para
estruturar o texto em JSON).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import os
import pytesseract
from PIL import Image
from pdf2image import convert_from_path

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
os.environ['TESSDATA_PREFIX'] = r'C:\Program Files\Tesseract-OCR\tessdata'

POPPLER_PATH = r'C:\poppler\Library\bin'


@dataclass
class ResultadoOCR:
    caso: str
    arquivo: str
    tempo_segundos: float
    n_caracteres_extraidos: int
    n_paginas: int
    amostra_texto: str


def _ocr_imagem(caminho: Path) -> str:
    img = Image.open(caminho)
    return pytesseract.image_to_string(img, lang="por")


def _ocr_pdf(caminho: Path, pagina: int, dpi: int = 150) -> str:
    """Rasteriza e faz OCR em UMA unica pagina..."""
    # ADICIONE o argumento poppler_path aqui:
    imagens = convert_from_path(
        str(caminho), 
        dpi=dpi, 
        first_page=pagina, 
        last_page=pagina,
        poppler_path=POPPLER_PATH  # <-- NOVA LINHA AQUI
    )
    texto = pytesseract.image_to_string(imagens[0], lang="eng") if imagens else ""
    return texto

def rodar_baseline(diretorio_samples: str | Path = "samples") -> list[ResultadoOCR]:
    diretorio_samples = Path(diretorio_samples)
    resultados = []

    # Caso 1: CNH (imagem)
    caminho = diretorio_samples / "cnh_exemplo.jpeg"
    t0 = time.perf_counter()
    texto = _ocr_imagem(caminho)
    dt = time.perf_counter() - t0
    resultados.append(
        ResultadoOCR(
            caso="cnh",
            arquivo=caminho.name,
            tempo_segundos=round(dt, 3),
            n_caracteres_extraidos=len(texto.strip()),
            n_paginas=1,
            amostra_texto=texto.strip()[:600],
        )
    )

    # Caso 2: fatura de energia (imagem, layout tabular denso)
    caminho = diretorio_samples / "fatura_energia.jpg"
    t0 = time.perf_counter()
    texto = _ocr_imagem(caminho)
    dt = time.perf_counter() - t0
    resultados.append(
        ResultadoOCR(
            caso="fatura",
            arquivo=caminho.name,
            tempo_segundos=round(dt, 3),
            n_caracteres_extraidos=len(texto.strip()),
            n_paginas=1,
            amostra_texto=texto.strip()[:600],
        )
    )

    # Caso 3a: documento extenso (PDF, pagina 8 = tabela densa de benchmarks)
    caminho = diretorio_samples / "claude3_model_family.pdf"
    t0 = time.perf_counter()
    texto = _ocr_pdf(caminho, pagina=8, dpi=150)
    dt = time.perf_counter() - t0
    resultados.append(
        ResultadoOCR(
            caso="documento_extenso_pg8_tabela",
            arquivo=caminho.name + " (pg. 8)",
            tempo_segundos=round(dt, 3),
            n_caracteres_extraidos=len(texto.strip()),
            n_paginas=1,
            amostra_texto=texto.strip()[:600],
        )
    )

    # Caso 3b: mesma logica, na pagina do GRAFICO (pg. 9) -- para evidenciar
    # que OCR classico nao interpreta conteudo visual nao-textual.
    t0 = time.perf_counter()
    texto = _ocr_pdf(caminho, pagina=9, dpi=150)
    dt = time.perf_counter() - t0
    resultados.append(
        ResultadoOCR(
            caso="documento_extenso_pg9_grafico",
            arquivo=caminho.name + " (pg. 9)",
            tempo_segundos=round(dt, 3),
            n_caracteres_extraidos=len(texto.strip()),
            n_paginas=1,
            amostra_texto=texto.strip()[:600],
        )
    )

    return resultados


if __name__ == "__main__":
    resultados = rodar_baseline()
    saida = [asdict(r) for r in resultados]
    with open("outputs/baseline_ocr_resultados.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    for r in resultados:
        print("=" * 70)
        print(f"Caso: {r.caso} | tempo={r.tempo_segundos}s | chars={r.n_caracteres_extraidos} | paginas={r.n_paginas}")
        print("--- amostra do texto bruto extraido (sem estrutura/JSON) ---")
        print(r.amostra_texto)
        print()
    print("Resultados completos salvos em outputs/baseline_ocr_resultados.json")
