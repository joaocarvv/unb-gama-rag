"""Valida o catálogo de fontes. Sai com código 1 se houver erro.

Uso: python scripts/03_validar_catalogo.py
"""

import sys

from unb_gama_rag.catalogo import ler_catalogo, resumo_status, validar_catalogo
from unb_gama_rag.config import caminho_projeto, carregar_config


def main() -> int:
    config = carregar_config()
    regras = config["catalogo"]
    caminho = caminho_projeto(config["caminhos"]["catalogo"])

    fontes = ler_catalogo(caminho)
    problemas = validar_catalogo(fontes, regras)
    status = resumo_status(fontes)

    print(f"Catálogo: {config['caminhos']['catalogo']}")
    print(f"{len(fontes)} fontes: " + ", ".join(f"{n} {s}" for s, n in sorted(status.items())))

    aprovadas = status.get("aprovado", 0)
    meta = regras["meta_aprovados"]
    falta = max(meta - aprovadas, 0)
    print(f"Meta: {meta} aprovadas ({aprovadas} hoje, faltam {falta})")

    if problemas:
        print(f"\n{len(problemas)} problema(s):")
        for problema in problemas:
            print(f"  - {problema}")
        return 1

    print("\nNenhum problema encontrado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
