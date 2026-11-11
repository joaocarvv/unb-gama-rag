"""Reabre o índice SEM ingerir nada e confere se ele está íntegro.

Uso:
  python scripts/06_conferir.py              índice real
  python scripts/06_conferir.py --rascunho   índice de rascunho

Confere: total e ids iguais ao manifesto e ao arquivo de chunks, dimensão,
distância, configuração e se o vetor salvo bate com o modelo atual.
Depois roda as perguntas de conferência do rag.yaml e mostra o ranking.
"""

import argparse
import json
import sys

from unb_gama_rag.config import caminho_projeto, carregar_config
from unb_gama_rag.embeddings import EmbedderE5
from unb_gama_rag.indice import SEPARADOR, abrir_cliente, abrir_colecao, buscar, distancia_da_colecao
from unb_gama_rag.manifesto import esperado_pela_config, incompatibilidades, ler_manifesto


def main() -> int:
    parser = argparse.ArgumentParser(description="Reabre e confere o índice.")
    parser.add_argument("--rascunho", action="store_true", help="confere o índice de rascunho")
    args = parser.parse_args()

    config = carregar_config()
    caminhos = config["caminhos"]
    sufixo = "_rascunho" if args.rascunho else ""
    manifesto = ler_manifesto(caminho_projeto(caminhos["manifesto" + sufixo]))
    if manifesto is None:
        print("Manifesto não encontrado. Rode antes scripts/05_indexar.py.")
        return 1

    checagens = []

    def checar(nome, ok, detalhe=""):
        checagens.append(ok)
        print(f"  [{'ok' if ok else 'FALHOU'}] {nome}" + (f": {detalhe}" if detalhe else ""))

    print("Conferência do índice (reaberto do disco, sem ingestão)")
    cliente = abrir_cliente(caminho_projeto(caminhos["chroma" + sufixo]))
    try:
        colecao = abrir_colecao(cliente, config["indice"]["colecao"], config["indice"]["distancia"], criar=False)
    except Exception as erro:  # coleção não existe
        print(f"  [FALHOU] abrir coleção: {erro}")
        return 1

    diferencas = incompatibilidades(manifesto, esperado_pela_config(config))
    checar("config atual compatível com o manifesto", not diferencas, "; ".join(diferencas))

    total = colecao.count()
    checar("total igual ao manifesto", total == manifesto["total_chunks"],
           f"{total} no índice, {manifesto['total_chunks']} no manifesto")

    arquivo_chunks = caminho_projeto(caminhos["chunks" + sufixo])
    with open(arquivo_chunks, encoding="utf-8") as arquivo:
        chunks = {c["chunk_id"]: c for c in map(json.loads, filter(str.strip, arquivo))}
    ids_indice = set(colecao.get(include=[])["ids"])
    faltando, sobrando = set(chunks) - ids_indice, ids_indice - set(chunks)
    checar("ids iguais ao arquivo de chunks", not faltando and not sobrando,
           f"{len(faltando)} faltando, {len(sobrando)} sobrando")

    distancia = distancia_da_colecao(colecao)
    checar("distância da coleção", distancia == config["indice"]["distancia"], distancia)

    amostra_id = sorted(ids_indice)[0]
    salvo = colecao.get(ids=[amostra_id], include=["embeddings"])["embeddings"][0]
    checar("dimensão dos vetores", len(salvo) == config["embeddings"]["dimensao"], str(len(salvo)))

    print("Carregando o modelo para recodificar uma amostra e rodar as perguntas...")
    embedder = EmbedderE5(config["embeddings"])
    recodificado = embedder.codificar_documentos([chunks[amostra_id]["texto"]])[0]
    diferenca = max(abs(a - b) for a, b in zip(salvo, recodificado))
    tolerancia = config["conferencia"]["tolerancia_vetor"]
    checar("vetor salvo bate com o modelo atual", diferenca <= tolerancia,
           f"{amostra_id}, diferença máxima {diferenca:.2e}")

    top_k = config["busca"]["top_k"]
    print(f"\nPerguntas de conferência (top {top_k}, sem filtros; isso não é avaliação)")
    for pergunta in config["conferencia"]["perguntas"]:
        print(f"\n> {pergunta}")
        for item in buscar(colecao, embedder.codificar_pergunta(pergunta), top_k):
            secao = item["secoes"].replace(SEPARADOR, "; ") or "(sem título de seção)"
            print(f"  {item['colocacao']}. {item['distancia']:.4f}  {item['chunk_id']}  {item['source_id']} "
                  f"v{item['versao']}  {item['titulo']} > {secao}")

    falhas = checagens.count(False)
    print(f"\n{len(checagens) - falhas} de {len(checagens)} checagens ok."
          f" Distância cosseno: menor = mais parecido. Não é probabilidade de estar certo.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
