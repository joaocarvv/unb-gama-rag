"""Extração: transforma o HTML original em texto limpo, organizado por seção.

Regras:
- Pega só a área de conteúdo (seletor configurado) e remove menu, rodapé, scripts etc.
- Texto dentro de um mesmo bloco (parágrafo, item de lista) fica num parágrafo só,
  mesmo que tenha links ou negrito no meio. <br> vira quebra de linha dentro dele.
- Títulos de abas (sanfonas) viram títulos de seção do nível mais fundo (h6).
- Cada seção guarda o caminho de títulos acima dela, para o texto não perder o contexto.
- Não reescreve conteúdo: só remove marcação e espaços repetidos.
"""

import re

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

TITULOS = {f"h{n}": n for n in range(1, 7)}
BLOCOS = {
    "p", "div", "section", "article", "main", "li", "ul", "ol", "dl", "dt", "dd",
    "table", "thead", "tbody", "tr", "td", "th", "blockquote", "figure", "figcaption",
    "hr", "pre", "address",
}


class ErroExtracao(Exception):
    pass


def regras_para(config_extracao: dict, dominio: str, source_id: str) -> dict:
    """Junta as regras padrão com as do site e as da fonte."""
    site = config_extracao["por_site"].get(dominio, {})
    fonte = (config_extracao.get("por_fonte") or {}).get(source_id, {})
    return {
        "conteudo": site.get("conteudo", config_extracao["conteudo_padrao"]),
        "remover": config_extracao["remover_padrao"] + site.get("remover", []) + fonte.get("remover", []),
        "titulos_extras": config_extracao["titulos_extras"],
    }


def _normalizar(texto: str) -> str:
    return " ".join(texto.split())


def _percorrer(no: Tag, itens: list, linha: list) -> None:
    """Gera itens ("titulo", nivel, texto) e ("texto", texto) na ordem do documento."""

    def fechar():
        linhas = (_normalizar(parte) for parte in "".join(linha).split("\n"))
        texto = "\n".join(parte for parte in linhas if parte)
        if texto:
            itens.append(("texto", texto))
        linha.clear()

    for filho in no.children:
        if isinstance(filho, Comment):
            continue
        if isinstance(filho, NavigableString):
            linha.append(re.sub(r"\s+", " ", str(filho)))  # quebra de linha do código-fonte vira espaço
        elif filho.name == "br":
            linha.append("\n")
        elif filho.name in TITULOS:
            fechar()
            texto = _normalizar(filho.get_text(" "))
            if texto:
                itens.append(("titulo", TITULOS[filho.name], texto))
        elif filho.name in BLOCOS:
            fechar()
            _percorrer(filho, itens, linha)
            fechar()
        else:  # elemento de linha: a, strong, span, em...
            _percorrer(filho, itens, linha)
    if no.name in BLOCOS:
        fechar()


def _montar_secoes(itens: list) -> tuple[list[dict], int]:
    """Agrupa parágrafos sob o caminho de títulos. Remove repetição consecutiva."""
    secoes: list[dict] = []
    pilha: list[tuple[int, str]] = []  # (nivel, titulo)
    atual = None
    removidos = 0

    for item in itens:
        if item[0] == "titulo":
            _, nivel, texto = item
            while pilha and pilha[-1][0] >= nivel:
                pilha.pop()
            pilha.append((nivel, texto))
            atual = None
            continue

        texto = item[1]
        if atual is None:
            atual = {"caminho": [t for _, t in pilha], "paragrafos": []}
            secoes.append(atual)
        repetido = (atual["paragrafos"] and atual["paragrafos"][-1] == texto) or (
            atual["caminho"] and atual["caminho"][-1] == texto
        )
        if repetido:
            removidos += 1
        else:
            atual["paragrafos"].append(texto)

    return [s for s in secoes if s["paragrafos"]], removidos


def extrair_html(html: bytes, regras: dict, min_palavras: int) -> dict:
    sopa = BeautifulSoup(html, "lxml")
    titulo_pagina = _normalizar(sopa.title.get_text()) if sopa.title else ""

    area = sopa.select_one(regras["conteudo"])
    if area is None:
        raise ErroExtracao(f"área de conteúdo '{regras['conteudo']}' não encontrada")

    for seletor in regras["remover"]:
        for elemento in area.select(seletor):
            elemento.decompose()

    for seletor in regras["titulos_extras"]:
        for elemento in area.select(seletor):
            elemento.name = "h6"

    itens: list = []
    _percorrer(area, itens, [])
    secoes, removidos = _montar_secoes(itens)

    palavras = sum(len(p.split()) for s in secoes for p in s["paragrafos"])
    avisos = []
    if palavras < min_palavras:
        avisos.append(f"pouco texto: {palavras} palavras")

    return {
        "titulo_pagina": titulo_pagina,
        "palavras": palavras,
        "repeticoes_removidas": removidos,
        "avisos": avisos,
        "secoes": secoes,
    }
