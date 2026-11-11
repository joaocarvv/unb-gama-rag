"""Gera os embeddings dos chunks e sincroniza o índice Chroma.

Uso:
  python scripts/05_indexar.py                  chunks.jsonl (aprovadas) -> data/index/chroma
  python scripts/05_indexar.py --rascunho       chunks_rascunho.jsonl -> data/index/chroma_rascunho
  python scripts/05_indexar.py --reconstruir    apaga a coleção e indexa tudo de novo

Rodar de novo com os mesmos chunks não duplica nada: só codifica ids novos,
atualiza metadados dos que já existem e remove os que sumiram.
"""

import argparse
import json
import sys
import time

from unb_gama_rag.config import caminho_projeto, carregar_config
from unb_gama_rag.embeddings import EmbedderE5
from unb_gama_rag.indice import abrir_cliente, abrir_colecao, apagar_colecao, sincronizar
from unb_gama_rag.manifesto import (
    esperado_pela_config,
    gravar_manifesto,
    incompatibilidades,
    ler_manifesto,
    montar_manifesto,
)


class EmbedderSobDemanda:
    """Só carrega o modelo se houver chunk novo para codificar."""

    def __init__(self, config_embeddings):
        self._config = config_embeddings
        self._embedder = None
        self.segundos_carga = 0.0

    def codificar_documentos(self, textos):
        if self._embedder is None:
            print("Carregando o modelo de embeddings (na 1ª vez ele é baixado)...")
            inicio = time.perf_counter()
            self._embedder = EmbedderE5(self._config)
            self.segundos_carga = time.perf_counter() - inicio
        return self._embedder.codificar_documentos(textos)


def ler_chunks(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return [json.loads(linha) for linha in arquivo if linha.strip()]


def conferir_chunks(chunks, registro, rascunho) -> list[str]:
    erros = []
    if len(chunks) != registro["total_chunks"]:
        erros.append(f"arquivo tem {len(chunks)} chunks, o .config.json diz {registro['total_chunks']}")
    configs = {c["config_chunking"] for c in chunks}
    if configs != {registro["config_chunking"]}:
        erros.append(f"chunks com configs diferentes: {sorted(configs)}")
    if registro["rascunho"] != rascunho:
        erros.append("arquivo de chunks não corresponde ao modo (rascunho ou real)")
    if not rascunho:
        nao_aprovados = sorted({c["source_id"] for c in chunks if c["status"] != "aprovado"})
        if nao_aprovados:
            erros.append(f"índice real só aceita aprovadas, mas há: {', '.join(nao_aprovados)}")
    return erros


def main() -> int:
    parser = argparse.ArgumentParser(description="Indexa os chunks no Chroma.")
    parser.add_argument("--rascunho", action="store_true", help="usa chunks e índice de rascunho")
    parser.add_argument("--reconstruir", action="store_true", help="apaga a coleção e indexa do zero")
    args = parser.parse_args()

    config = carregar_config()
    caminhos = config["caminhos"]
    sufixo = "_rascunho" if args.rascunho else ""
    arquivo_chunks = caminho_projeto(caminhos["chunks" + sufixo])
    arquivo_registro = arquivo_chunks.with_name(arquivo_chunks.stem + ".config.json")
    pasta_indice = caminho_projeto(caminhos["chroma" + sufixo])
    arquivo_manifesto = caminho_projeto(caminhos["manifesto" + sufixo])
    nome_colecao = config["indice"]["colecao"]

    if not arquivo_chunks.exists() or not arquivo_registro.exists():
        opcao = " --rascunho" if args.rascunho else ""
        print(f"{arquivo_chunks.name} não encontrado. Rode antes: python scripts/04_chunks.py{opcao}")
        return 1
    chunks = ler_chunks(arquivo_chunks)
    registro = json.loads(arquivo_registro.read_text(encoding="utf-8"))
    erros = conferir_chunks(chunks, registro, args.rascunho)
    if erros:
        print("Problemas nos chunks:")
        for erro in erros:
            print(f"  - {erro}")
        return 1

    cliente = abrir_cliente(pasta_indice)
    manifesto_antigo = ler_manifesto(arquivo_manifesto)
    if args.reconstruir:
        if apagar_colecao(cliente, nome_colecao):
            print(f"Coleção '{nome_colecao}' apagada para reconstrução.")
    elif manifesto_antigo:
        diferencas = incompatibilidades(manifesto_antigo, esperado_pela_config(config))
        if diferencas:
            print("O índice existente foi gerado com outra configuração:")
            for diferenca in diferencas:
                print(f"  - {diferenca}")
            print("Vetores diferentes não se comparam. Rode de novo com --reconstruir.")
            return 1

    colecao = abrir_colecao(cliente, nome_colecao, config["indice"]["distancia"])
    if not args.reconstruir and manifesto_antigo is None and colecao.count() > 0:
        print("Há chunks no índice mas não há manifesto: não dá para saber como foram gerados.")
        print("Rode de novo com --reconstruir.")
        return 1

    embedder = EmbedderSobDemanda(config["embeddings"])
    inicio = time.perf_counter()
    resultado = sincronizar(colecao, chunks, embedder, config["embeddings"]["lote"])
    segundos = time.perf_counter() - inicio

    if resultado["total"] != len(chunks):
        print(f"Erro: índice ficou com {resultado['total']} chunks, esperado {len(chunks)}.")
        return 1

    raiz = caminho_projeto(".")
    manifesto = montar_manifesto(config, registro, nome_colecao,
                                 pasta_indice.relative_to(raiz).as_posix(), resultado, args.rascunho)
    gravar_manifesto(arquivo_manifesto, manifesto)

    print(f"novos (codificados): {resultado['novos']}")
    print(f"mantidos (só metadados atualizados): {resultado['mantidos']}")
    print(f"removidos (versões superadas): {resultado['removidos']}")
    print(f"total no índice: {resultado['total']}")
    if embedder.segundos_carga:
        print(f"tempo: {embedder.segundos_carga:.1f}s carregando o modelo, "
              f"{segundos - embedder.segundos_carga:.1f}s codificando e gravando")
    print(f"versão do corpus: {manifesto['corpus']['versao']}")
    print(f"Índice em {manifesto['indice']['caminho']}, manifesto em "
          f"{arquivo_manifesto.relative_to(raiz).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
