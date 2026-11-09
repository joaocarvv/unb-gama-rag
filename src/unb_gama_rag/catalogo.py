"""Leitura e validação do catálogo de fontes (catalogo/fontes.csv).

O catálogo é a tabela de controle das fontes: só o que está aqui, com status
aprovado, segue para o pipeline. A validação barra linhas mal preenchidas antes
que virem chunks.
"""

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

COLUNAS = [
    "source_id", "titulo", "tipo", "url", "campus", "abrangencia", "descricao",
    "data_coleta", "data_revisao", "validade", "revisor", "status", "motivo",
    "sha256", "versao", "limitacoes", "relacoes", "condicoes_uso",
]

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Campos que uma fonte aprovada precisa ter preenchidos.
OBRIGATORIOS_APROVADO = ["data_coleta", "data_revisao", "revisor", "sha256", "versao"]


@dataclass
class Problema:
    linha: int  # linha no arquivo, com o cabeçalho na linha 1
    source_id: str
    mensagem: str

    def __str__(self) -> str:
        return f"linha {self.linha} ({self.source_id or 'sem id'}): {self.mensagem}"


def ler_catalogo(caminho: Path | str) -> list[dict]:
    """Lê o CSV e devolve uma lista de dicionários com valores sem espaços nas pontas."""
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        faltando = [c for c in COLUNAS if c not in (leitor.fieldnames or [])]
        if faltando:
            raise ValueError(f"colunas ausentes no catálogo: {', '.join(faltando)}")
        return [{k: (v or "").strip() for k, v in linha.items()} for linha in leitor]


def _data_valida(texto: str) -> bool:
    try:
        date.fromisoformat(texto)
        return len(texto) == 10  # exige AAAA-MM-DD
    except ValueError:
        return False


def validar_fonte(fonte: dict, regras: dict) -> list[str]:
    """Regras de uma linha isolada. Devolve mensagens de erro."""
    erros = []

    for campo in ["source_id", "titulo", "tipo", "url", "abrangencia", "validade", "status"]:
        if not fonte[campo]:
            erros.append(f"campo '{campo}' vazio")

    if fonte["tipo"] and fonte["tipo"] not in regras["tipos_validos"]:
        erros.append(f"tipo '{fonte['tipo']}' inválido (use {regras['tipos_validos']})")

    if fonte["tipo"] == "pagina_web" and fonte["url"] and not fonte["url"].startswith(("http://", "https://")):
        erros.append("página web precisa de URL começando com http:// ou https://")

    if fonte["abrangencia"] and fonte["abrangencia"] not in regras["abrangencias_validas"]:
        erros.append(
            f"abrangência '{fonte['abrangencia']}' inválida (use {regras['abrangencias_validas']})"
        )

    if fonte["abrangencia"] == "Gama" and fonte["campus"] != "Gama":
        erros.append("abrangência Gama exige campus Gama")

    if fonte["status"] and fonte["status"] not in regras["status_validos"]:
        erros.append(f"status '{fonte['status']}' inválido (use {regras['status_validos']})")

    if fonte["status"] == "rejeitado" and not fonte["motivo"]:
        erros.append("fonte rejeitada precisa de motivo")

    for campo in ["data_coleta", "data_revisao"]:
        if fonte[campo] and not _data_valida(fonte[campo]):
            erros.append(f"'{campo}' fora do formato AAAA-MM-DD: {fonte[campo]}")

    validade = fonte["validade"]
    if validade and validade != regras["validade_desconhecida"]:
        if not _data_valida(validade):
            erros.append(
                f"validade deve ser AAAA-MM-DD ou '{regras['validade_desconhecida']}': {validade}"
            )
        elif validade == fonte["data_coleta"]:
            erros.append("validade igual à data de coleta: use 'desconhecida' se não houver validade")

    if fonte["sha256"] and not SHA256_RE.match(fonte["sha256"]):
        erros.append("sha256 deve ter 64 caracteres hexadecimais minúsculos")

    if fonte["status"] == "aprovado":
        for campo in OBRIGATORIOS_APROVADO:
            if not fonte[campo]:
                erros.append(f"fonte aprovada precisa de '{campo}'")

    return erros


def validar_catalogo(fontes: list[dict], regras: dict) -> list[Problema]:
    """Valida cada linha e as regras que dependem do catálogo inteiro."""
    problemas = []
    ids = [f["source_id"] for f in fontes]

    vistos = set()
    for i, fonte in enumerate(fontes):
        linha = i + 2
        sid = fonte["source_id"]

        for mensagem in validar_fonte(fonte, regras):
            problemas.append(Problema(linha, sid, mensagem))

        if sid and sid in vistos:
            problemas.append(Problema(linha, sid, "source_id duplicado"))
        vistos.add(sid)

        for relacionado in filter(None, (r.strip() for r in fonte["relacoes"].split(";"))):
            if relacionado not in ids:
                problemas.append(Problema(linha, sid, f"relação com '{relacionado}', que não existe no catálogo"))

    return problemas


def resumo_status(fontes: list[dict]) -> dict[str, int]:
    contagem: dict[str, int] = {}
    for fonte in fontes:
        contagem[fonte["status"]] = contagem.get(fonte["status"], 0) + 1
    return contagem
