"""Gera os chunks a partir dos documentos extraídos.

Uso:
  python scripts/04_chunks.py                         só fontes aprovadas -> chunks.jsonl
  python scripts/04_chunks.py --rascunho              pendentes como se aprovadas -> chunks_rascunho.jsonl
  python scripts/04_chunks.py --rascunho --estrategia por_secao   testa a opção A
  python scripts/04_chunks.py --rascunho --mostrar DOC-015        imprime os chunks de uma fonte
"""

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from importlib.metadata import version

from unb_gama_rag.catalogo import ler_catalogo
from unb_gama_rag.chunking import ESTRATEGIAS, ErroChunking, gerar_chunks, id_config
from unb_gama_rag.config import caminho_projeto, carregar_config
from unb_gama_rag.normalizacao import carregar_entidades, compilar, marcar, validar_entidades
from unb_gama_rag.tokens import ContadorTokens


def mostrar(caminho, source_id) -> None:
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        chunk = json.loads(linha)
        if chunk["source_id"] == source_id:
            print(f"--- {chunk['chunk_id']} | posição {chunk['posicao']} | {chunk['tokens']} tokens")
            print(chunk["texto"] + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera chunks dos documentos extraídos.")
    parser.add_argument("--rascunho", action="store_true", help="incluir pendentes (não vai para o índice real)")
    parser.add_argument("--estrategia", choices=ESTRATEGIAS, help="sobrescreve a estratégia do rag.yaml")
    parser.add_argument("--mostrar", metavar="SOURCE_ID", help="imprime os chunks já gerados de uma fonte")
    args = parser.parse_args()

    config = carregar_config()
    chunking = dict(config["chunking"])
    if args.estrategia:
        chunking["estrategia"] = args.estrategia
    embeddings = config["embeddings"]
    destino = caminho_projeto(config["caminhos"]["chunks_rascunho" if args.rascunho else "chunks"])

    if args.mostrar:
        if not destino.exists():
            print(f"{destino.name} ainda não existe.")
            return 1
        mostrar(destino, args.mostrar)
        return 0

    fontes = ler_catalogo(caminho_projeto(config["caminhos"]["catalogo"]))
    ignorados = config["aquisicao"]["status_ignorados"]
    if args.rascunho:
        selecionadas = [f for f in fontes if f["status"] not in ignorados]
    else:
        selecionadas = [f for f in fontes if f["status"] == "aprovado"]
    if not selecionadas:
        print("Nenhuma fonte aprovada no catálogo. Para testar com as pendentes, use --rascunho.")
        return 1

    entidades = carregar_entidades(caminho_projeto(config["caminhos"]["entidades"]))
    erros_entidades = validar_entidades(entidades, {f["source_id"] for f in fontes})
    if erros_entidades:
        print("Problemas em entidades.yaml:")
        for erro in erros_entidades:
            print(f"  - {erro}")
        return 1
    compiladas = compilar(entidades)

    conta = ContadorTokens(embeddings["modelo"], embeddings["revisao"])
    pasta_extraido = caminho_projeto(config["caminhos"]["extraido"])

    todos, resumo, erros = [], [], 0
    for fonte in selecionadas:
        sid = fonte["source_id"]
        arquivo = pasta_extraido / f"{sid}__{fonte['versao']}.json"
        if not arquivo.exists():
            print(f"{sid:8} erro: extraído não encontrado, rode scripts/02_extrair.py")
            erros += 1
            continue
        documento = json.loads(arquivo.read_text(encoding="utf-8"))
        if documento["sha256_original"] != fonte["sha256"]:
            print(f"{sid:8} erro: extraído veio de outro original (SHA diferente do catálogo)")
            erros += 1
            continue
        try:
            chunks = gerar_chunks(documento, fonte, conta, chunking, embeddings, args.rascunho)
        except ErroChunking as erro:
            print(f"{sid:8} erro: {erro}")
            erros += 1
            continue
        for chunk in chunks:
            chunk["entidades"] = marcar(chunk["texto"], compiladas)
        tokens = [c["tokens"] for c in chunks]
        print(f"{sid:8} {len(chunks):3} chunks  tokens: min {min(tokens):3}  max {max(tokens):3}")
        todos.extend(chunks)
        resumo.append({"source_id": sid, "versao": fonte["versao"], "sha256": fonte["sha256"], "chunks": len(chunks)})

    if erros:
        print(f"\n{erros} erro(s). Nada foi gravado.")
        return 1

    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="\n") as saida:
        for chunk in todos:
            saida.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    tokens = [c["tokens"] for c in todos]
    registro = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rascunho": args.rascunho,
        "chunking": chunking,
        "config_chunking": id_config(chunking, embeddings),
        "tokenizer": {"modelo": embeddings["modelo"], "revisao": embeddings["revisao"],
                      "tokenizers": version("tokenizers")},
        "total_chunks": len(todos),
        "tokens": {"min": min(tokens), "mediana": statistics.median(tokens), "max": max(tokens)},
        "fontes": resumo,
    }
    destino.with_name(destino.stem + ".config.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"\n{len(todos)} chunks de {len(resumo)} fontes ({chunking['estrategia']})")
    print(f"tokens por chunk: min {min(tokens)}, mediana {statistics.median(tokens)}, max {max(tokens)}"
          f" (alvo {chunking['alvo_tokens']}, máximo {chunking['max_tokens']})")
    com_entidade = sum(1 for c in todos if c["entidades"])
    print(f"chunks com ao menos uma entidade: {com_entidade} de {len(todos)}")
    print(f"Gravado em {destino.relative_to(caminho_projeto('.'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
