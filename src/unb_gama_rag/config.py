"""Carrega a configuração central (config/rag.yaml)."""

from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
CONFIG_PADRAO = RAIZ / "config" / "rag.yaml"


def carregar_config(caminho: Path | str | None = None) -> dict:
    caminho = Path(caminho) if caminho else CONFIG_PADRAO
    with open(caminho, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def caminho_projeto(relativo: str) -> Path:
    """Transforma um caminho do rag.yaml (relativo à raiz) em caminho absoluto."""
    return RAIZ / relativo
