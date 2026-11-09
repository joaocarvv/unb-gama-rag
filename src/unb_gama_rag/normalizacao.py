"""Normalização: marca quais entidades (prédios, laboratórios, serviços) cada chunk menciona.

Não altera o texto. Só devolve a lista de IDs de entidades encontradas,
que vai para os metadados do chunk.
"""

import re
from pathlib import Path

import yaml

# Letras (inclusive acentuadas) e dígitos: uma variante não pode estar colada a eles.
_BORDA_ANTES = r"(?<![0-9A-Za-zÀ-ÿ])"
_BORDA_DEPOIS = r"(?![0-9A-Za-zÀ-ÿ])"


def carregar_entidades(caminho: Path | str) -> list[dict]:
    with open(caminho, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)["entidades"]


def validar_entidades(entidades: list[dict], ids_fontes: set[str]) -> list[str]:
    erros = []
    vistos: set[str] = set()
    dono_variante: dict[str, str] = {}
    for entidade in entidades:
        eid = entidade.get("id", "")
        if not eid:
            erros.append(f"entidade sem id: {entidade}")
            continue
        if eid in vistos:
            erros.append(f"{eid}: id duplicado")
        vistos.add(eid)
        for campo in ["tipo", "nome", "variantes", "fonte"]:
            if not entidade.get(campo):
                erros.append(f"{eid}: campo '{campo}' vazio")
        if entidade.get("fonte") and entidade["fonte"] not in ids_fontes:
            erros.append(f"{eid}: fonte {entidade['fonte']} não existe no catálogo")
        for variante in entidade.get("variantes") or []:
            chave = variante.casefold()
            if chave in dono_variante and dono_variante[chave] != eid:
                erros.append(f"variante '{variante}' está em {dono_variante[chave]} e {eid}")
            dono_variante[chave] = eid
    return erros


def compilar(entidades: list[dict]) -> list[tuple[str, re.Pattern]]:
    """Uma expressão regular por entidade, com todas as variantes."""
    compiladas = []
    for entidade in entidades:
        partes = []
        for variante in entidade["variantes"]:
            padrao = _BORDA_ANTES + re.escape(variante) + _BORDA_DEPOIS
            # sigla (sem espaço): exata; nome (com espaço): ignora maiúsculas
            partes.append(padrao if " " not in variante else f"(?i:{padrao})")
        compiladas.append((entidade["id"], re.compile("|".join(partes))))
    return compiladas


def marcar(texto: str, compiladas: list[tuple[str, re.Pattern]]) -> list[str]:
    return sorted(eid for eid, padrao in compiladas if padrao.search(texto))
