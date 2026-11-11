"""Manifesto do índice: registra com o que os vetores foram gerados.

Vetores de modelos (ou prefixos, ou distâncias) diferentes não se comparam.
Se algo disso mudar, o índice precisa ser reconstruído do zero.
"""

import hashlib
import json
import platform
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

BIBLIOTECAS = ["sentence-transformers", "transformers", "torch", "tokenizers", "chromadb", "numpy"]

# (seção, campo) que, se mudarem, tornam os vetores antigos incompatíveis
CAMPOS_INCOMPATIVEIS = [
    ("embeddings", "modelo"),
    ("embeddings", "revisao"),
    ("embeddings", "dimensao"),
    ("embeddings", "prefixo_documento"),
    ("embeddings", "normalizar"),
    ("indice", "distancia"),
]


def versoes_bibliotecas() -> dict:
    versoes = {"python": platform.python_version()}
    for nome in BIBLIOTECAS:
        try:
            versoes[nome] = version(nome)
        except PackageNotFoundError:
            versoes[nome] = None
    return versoes


def versao_corpus(fontes: list[dict]) -> str:
    """Hash das fontes usadas (id, versão, SHA). Mesma base, mesmo valor."""
    chave = sorted((f["source_id"], f["versao"], f["sha256"]) for f in fontes)
    return hashlib.sha256(json.dumps(chave).encode()).hexdigest()[:12]


def montar_manifesto(config: dict, registro_chunks: dict, colecao_nome: str,
                     caminho_indice: str, resultado: dict, rascunho: bool) -> dict:
    emb = config["embeddings"]
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rascunho": rascunho,
        "embeddings": {k: emb[k] for k in ["modelo", "revisao", "dimensao", "max_tokens",
                                           "prefixo_documento", "prefixo_pergunta", "normalizar"]},
        "tokenizer": registro_chunks["tokenizer"],
        "chunking": registro_chunks["chunking"],
        "config_chunking": registro_chunks["config_chunking"],
        "corpus": {
            "versao": versao_corpus(registro_chunks["fontes"]),
            "chunks_gerados_em": registro_chunks["gerado_em"],
            "fontes": registro_chunks["fontes"],
        },
        "indice": {"caminho": caminho_indice, "colecao": colecao_nome,
                   "distancia": config["indice"]["distancia"]},
        "bibliotecas": versoes_bibliotecas(),
        "total_chunks": resultado["total"],
        "ultima_execucao": {k: resultado[k] for k in ["novos", "mantidos", "removidos"]},
    }


def esperado_pela_config(config: dict) -> dict:
    """Só os campos que decidem compatibilidade, no mesmo formato do manifesto."""
    return {"embeddings": config["embeddings"], "indice": config["indice"]}


def incompatibilidades(manifesto: dict, esperado: dict) -> list[str]:
    diferencas = []
    for secao, campo in CAMPOS_INCOMPATIVEIS:
        antigo = manifesto.get(secao, {}).get(campo)
        novo = esperado.get(secao, {}).get(campo)
        if antigo != novo:
            diferencas.append(f"{secao}.{campo}: índice tem {antigo!r}, config pede {novo!r}")
    return diferencas


def ler_manifesto(caminho: Path) -> dict | None:
    if not caminho.exists():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


def gravar_manifesto(caminho: Path, manifesto: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
