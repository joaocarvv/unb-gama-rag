"""Extrai o texto limpo dos originais e grava em data/extraido/.

Uso:
  python scripts/02_extrair.py                  extrai todas as fontes baixadas
  python scripts/02_extrair.py --fonte DOC-001  só uma fonte
  python scripts/02_extrair.py --mostrar DOC-001  imprime o texto extraído (para revisão)
"""

import argparse
import json
import sys
from urllib.parse import urlsplit

from unb_gama_rag.aquisicao import NOME_ORIGINAL, pasta_versao
from unb_gama_rag.catalogo import ler_catalogo
from unb_gama_rag.config import caminho_projeto, carregar_config
from unb_gama_rag.extracao import ErroExtracao, extrair_html, regras_para


def mostrar(caminho) -> None:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    print(f"{dados['source_id']} | {dados['titulo_pagina']} | {dados['palavras']} palavras\n")
    for secao in dados["secoes"]:
        print("## " + (" > ".join(secao["caminho"]) or "(sem título)"))
        for paragrafo in secao["paragrafos"]:
            print("   " + paragrafo.replace("\n", "\n   "))
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrai texto limpo dos originais.")
    parser.add_argument("--fonte", help="source_id de uma fonte específica")
    parser.add_argument("--mostrar", metavar="SOURCE_ID", help="imprime o texto extraído de uma fonte")
    args = parser.parse_args()

    config = carregar_config()
    raiz_originais = caminho_projeto(config["caminhos"]["originais"])
    pasta_extraido = caminho_projeto(config["caminhos"]["extraido"])
    regras_extracao = config["extracao"]
    ignorados = config["aquisicao"]["status_ignorados"]

    fontes = ler_catalogo(caminho_projeto(config["caminhos"]["catalogo"]))

    if args.mostrar:
        fonte = next((f for f in fontes if f["source_id"] == args.mostrar), None)
        caminho = fonte and pasta_extraido / f"{fonte['source_id']}__{fonte['versao']}.json"
        if not caminho or not caminho.exists():
            print(f"{args.mostrar} ainda não foi extraída.")
            return 1
        mostrar(caminho)
        return 0

    pasta_extraido.mkdir(parents=True, exist_ok=True)
    erros = 0
    for fonte in fontes:
        sid = fonte["source_id"]
        if args.fonte and sid != args.fonte:
            continue
        if fonte["status"] in ignorados or fonte["tipo"] not in NOME_ORIGINAL:
            continue

        original = pasta_versao(raiz_originais, sid, fonte["versao"] or "?") / NOME_ORIGINAL[fonte["tipo"]]
        if not fonte["versao"] or not original.exists():
            print(f"{sid:8} erro      original não encontrado: rode scripts/01_adquirir.py")
            erros += 1
            continue

        regras = regras_para(regras_extracao, urlsplit(fonte["url"]).netloc, sid)
        try:
            resultado = extrair_html(original.read_bytes(), regras, regras_extracao["min_palavras"])
        except ErroExtracao as erro:
            print(f"{sid:8} erro      {erro}")
            erros += 1
            continue

        saida = {
            "source_id": sid,
            "versao": fonte["versao"],
            "sha256_original": fonte["sha256"],
            "url": fonte["url"],
            "regras": regras,
            **resultado,
        }
        destino = pasta_extraido / f"{sid}__{fonte['versao']}.json"
        destino.write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        print(f"{sid:8} extraido  {len(resultado['secoes']):3} seções, {resultado['palavras']:5} palavras")
        for aviso in resultado["avisos"]:
            print(f"{'':8} aviso: {aviso}")

    print(f"\nTexto extraído em {config['caminhos']['extraido']}/. Revise com --mostrar <source_id>.")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
