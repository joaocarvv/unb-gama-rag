"""Índice vetorial no Chroma.

Os vetores vêm do nosso Embedder, nunca da função padrão do Chroma.
Sincronizar = upsert por chunk_id + remover ids que não estão mais nos chunks.
Rodar de novo com os mesmos chunks não muda nada.
"""

from pathlib import Path

import chromadb
from chromadb.config import Settings

SEPARADOR = " | "


def abrir_cliente(caminho: Path | str):
    return chromadb.PersistentClient(path=str(caminho), settings=Settings(anonymized_telemetry=False))


def abrir_colecao(cliente, nome: str, distancia: str, criar: bool = True):
    """criar=False só reabre (para a conferência não criar coleção vazia sem querer)."""
    if not criar:
        return cliente.get_collection(nome, embedding_function=None)
    return cliente.get_or_create_collection(
        nome, metadata={"hnsw:space": distancia}, embedding_function=None
    )


def apagar_colecao(cliente, nome: str) -> bool:
    if nome in [c if isinstance(c, str) else c.name for c in cliente.list_collections()]:
        cliente.delete_collection(nome)
        return True
    return False


def distancia_da_colecao(colecao) -> str:
    return (colecao.metadata or {}).get("hnsw:space", "l2")


def metadados(chunk: dict) -> dict:
    """O Chroma só aceita texto, número e booleano: listas viram texto."""
    return {
        "source_id": chunk["source_id"],
        "versao": chunk["versao"],
        "sha256_original": chunk["sha256_original"],
        "titulo": chunk["titulo"],
        "url": chunk["url"],
        "secoes": SEPARADOR.join(chunk["secoes"]),
        "posicao": chunk["posicao"],
        "tokens": chunk["tokens"],
        "campus": chunk["campus"],
        "abrangencia": chunk["abrangencia"],
        "data_revisao": chunk["data_revisao"],
        "validade": chunk["validade"],
        "status": chunk["status"],
        "rascunho": chunk["rascunho"],
        "config_chunking": chunk["config_chunking"],
        "entidades": SEPARADOR.join(chunk.get("entidades", [])),
    }


def ids_no_indice(colecao) -> set[str]:
    return set(colecao.get(include=[])["ids"])


def _lotes(itens: list, tamanho: int):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def sincronizar(colecao, chunks: list[dict], embedder, lote: int) -> dict:
    """Deixa o índice exatamente igual à lista de chunks.

    - id novo: codifica e insere.
    - id que já existe: o texto é o mesmo (o id é hash da versão e da config),
      então não recodifica. Só atualiza metadados (ex.: status virou aprovado).
    - id que sumiu dos chunks (versão superada): remove.
    """
    ids = [c["chunk_id"] for c in chunks]
    if len(set(ids)) != len(ids):
        raise ValueError("chunk_id repetido no arquivo de chunks")

    existentes = ids_no_indice(colecao)
    novos = [c for c in chunks if c["chunk_id"] not in existentes]
    mantidos = [c for c in chunks if c["chunk_id"] in existentes]
    superados = sorted(existentes - set(ids))

    for grupo in _lotes(novos, lote):
        colecao.upsert(
            ids=[c["chunk_id"] for c in grupo],
            embeddings=embedder.codificar_documentos([c["texto"] for c in grupo]),
            documents=[c["texto"] for c in grupo],
            metadatas=[metadados(c) for c in grupo],
        )
    for grupo in _lotes(mantidos, lote):
        colecao.update(ids=[c["chunk_id"] for c in grupo], metadatas=[metadados(c) for c in grupo])
    for grupo in _lotes(superados, lote):
        colecao.delete(ids=grupo)

    return {"novos": len(novos), "mantidos": len(mantidos), "removidos": len(superados),
            "total": colecao.count()}


def buscar(colecao, vetor_pergunta: list[float], top_k: int) -> list[dict]:
    resultado = colecao.query(
        query_embeddings=[vetor_pergunta], n_results=top_k, include=["metadatas", "distances"]
    )
    return [
        # "colocacao" é a posição no ranking; "posicao" (do metadado) é a posição no documento
        {**meta, "colocacao": i + 1, "chunk_id": cid, "distancia": dist}
        for i, (cid, dist, meta) in enumerate(
            zip(resultado["ids"][0], resultado["distances"][0], resultado["metadatas"][0])
        )
    ]
