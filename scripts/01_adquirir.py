"""Baixa as fontes do catálogo e guarda os originais em data/originais/.

Uso:
  python scripts/01_adquirir.py                 baixa o que ainda não foi baixado
  python scripts/01_adquirir.py --fonte DOC-001 só uma fonte
  python scripts/01_adquirir.py --atualizar     baixa de novo e registra nova versão
"""

import argparse
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from unb_gama_rag.aquisicao import Robots, adquirir_fonte
from unb_gama_rag.catalogo import ler_catalogo, salvar_catalogo, validar_catalogo
from unb_gama_rag.config import caminho_projeto, carregar_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Baixa as fontes do catálogo.")
    parser.add_argument("--fonte", help="source_id de uma fonte específica")
    parser.add_argument("--atualizar", action="store_true", help="baixar de novo e registrar nova versão")
    args = parser.parse_args()

    config = carregar_config()
    regras = config["aquisicao"]
    caminho_catalogo = caminho_projeto(config["caminhos"]["catalogo"])
    raiz_originais = caminho_projeto(config["caminhos"]["originais"])

    fontes = ler_catalogo(caminho_catalogo)
    problemas = validar_catalogo(fontes, config["catalogo"])
    if problemas:
        print("Catálogo com problemas. Rode scripts/03_validar_catalogo.py e corrija antes de baixar.")
        return 1

    selecionadas = [f for f in fontes if not args.fonte or f["source_id"] == args.fonte]
    if not selecionadas:
        print(f"Fonte {args.fonte} não está no catálogo.")
        return 1

    agora = datetime.now(ZoneInfo(regras["fuso_horario"]))
    resultados = []
    with httpx.Client(
        headers={"User-Agent": regras["user_agent"]},
        timeout=regras["timeout_s"],
        follow_redirects=True,
    ) as cliente:
        robots = Robots(cliente, regras["user_agent"])
        for fonte in selecionadas:
            resultado = adquirir_fonte(
                fonte, cliente, robots, raiz_originais, agora,
                regras["status_ignorados"], args.atualizar,
            )
            resultados.append(resultado)
            print(f"{resultado.source_id:8} {resultado.situacao:9} {resultado.detalhe}")
            for aviso in resultado.avisos:
                print(f"{'':8} aviso: {aviso}")
            if resultado.situacao in ("baixado", "erro"):
                time.sleep(regras["pausa_s"])

    salvar_catalogo(caminho_catalogo, fontes)

    contagem: dict[str, int] = {}
    for r in resultados:
        contagem[r.situacao] = contagem.get(r.situacao, 0) + 1
    print("\nResumo: " + ", ".join(f"{n} {s}" for s, n in sorted(contagem.items())))
    print(f"Originais em {config['caminhos']['originais']}/ (fora do git)")
    return 1 if contagem.get("erro") else 0


if __name__ == "__main__":
    sys.exit(main())
