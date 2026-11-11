"""Testes de embeddings, índice e manifesto.

Usam o EmbedderFalso (sem baixar modelo) e um Chroma em pasta temporária.
Os chunks são de EXEMPLO, não são dados reais.
"""

import pytest
from chromadb.api.client import SharedSystemClient

from unb_gama_rag.embeddings import EmbedderFalso
from unb_gama_rag.indice import (
    abrir_cliente,
    abrir_colecao,
    apagar_colecao,
    buscar,
    distancia_da_colecao,
    ids_no_indice,
    metadados,
    sincronizar,
)
from unb_gama_rag.manifesto import esperado_pela_config, incompatibilidades, versao_corpus

CONFIG_EMB = {"modelo": "exemplo/modelo", "revisao": "abc", "dimensao": 64, "max_tokens": 512,
              "prefixo_documento": "passage: ", "prefixo_pergunta": "query: ", "normalizar": True,
              "lote": 2, "dispositivo": "cpu"}


def chunk(cid, texto, versao="2026-01-01", status="pendente"):
    return {"chunk_id": cid, "source_id": "EX-001", "versao": versao, "sha256_original": "0" * 64,
            "titulo": "Página de exemplo", "url": "https://exemplo.invalid/", "secoes": ["Labs", cid],
            "posicao": 0, "texto": texto, "tokens": 10, "campus": "Gama", "abrangencia": "Gama",
            "data_revisao": "", "validade": "desconhecida", "status": status, "rascunho": True,
            "config_chunking": "cfg", "entidades": ["lab-x"]}


CHUNKS = [
    chunk("c1", "laboratorio de foguetes sala 105"),
    chunk("c2", "biblioteca horario de funcionamento"),
    chunk("c3", "onibus linhas e horarios do campus"),
]


@pytest.fixture
def colecao(tmp_path):
    cliente = abrir_cliente(tmp_path / "chroma")
    yield abrir_colecao(cliente, "teste", "cosine")
    SharedSystemClient.clear_system_cache()


def test_prefixos_so_no_embedder():
    embedder = EmbedderFalso(CONFIG_EMB)
    embedder.codificar_documentos(["texto"])
    embedder.codificar_pergunta("pergunta")
    assert embedder.recebidos == ["passage: texto", "query: pergunta"]


def test_vetor_normalizado_e_dimensao():
    vetor = EmbedderFalso(CONFIG_EMB).codificar_pergunta("qualquer coisa")
    assert len(vetor) == 64
    assert abs(sum(v * v for v in vetor) - 1) < 1e-9


def test_rodar_duas_vezes_nao_duplica(colecao):
    embedder = EmbedderFalso(CONFIG_EMB)
    primeiro = sincronizar(colecao, CHUNKS, embedder, lote=2)
    segundo = sincronizar(colecao, CHUNKS, embedder, lote=2)
    assert primeiro == {"novos": 3, "mantidos": 0, "removidos": 0, "total": 3}
    assert segundo == {"novos": 0, "mantidos": 3, "removidos": 0, "total": 3}
    assert len(embedder.recebidos) == 3  # a 2ª rodada não recodificou nada


def test_versao_superada_sai_do_indice(colecao):
    embedder = EmbedderFalso(CONFIG_EMB)
    sincronizar(colecao, CHUNKS, embedder, lote=2)
    nova_versao = [CHUNKS[0], CHUNKS[1], chunk("c3-v2", "onibus linhas novas", versao="2026-02-01")]
    resultado = sincronizar(colecao, nova_versao, embedder, lote=2)
    assert resultado == {"novos": 1, "mantidos": 2, "removidos": 1, "total": 3}
    assert ids_no_indice(colecao) == {"c1", "c2", "c3-v2"}


def test_metadado_atualiza_sem_recodificar(colecao):
    embedder = EmbedderFalso(CONFIG_EMB)
    sincronizar(colecao, CHUNKS, embedder, lote=2)
    aprovados = [dict(c, status="aprovado") for c in CHUNKS]
    sincronizar(colecao, aprovados, embedder, lote=2)
    assert {m["status"] for m in colecao.get(include=["metadatas"])["metadatas"]} == {"aprovado"}
    assert len(embedder.recebidos) == 3


def test_reabrir_do_disco(tmp_path):
    embedder = EmbedderFalso(CONFIG_EMB)
    colecao = abrir_colecao(abrir_cliente(tmp_path / "chroma"), "teste", "cosine")
    sincronizar(colecao, CHUNKS, embedder, lote=2)
    SharedSystemClient.clear_system_cache()  # esquece o cliente em memória
    reaberta = abrir_colecao(abrir_cliente(tmp_path / "chroma"), "teste", "cosine", criar=False)
    assert reaberta.count() == 3
    assert distancia_da_colecao(reaberta) == "cosine"
    SharedSystemClient.clear_system_cache()


def test_distancia_e_cosseno(colecao):
    # vetores perpendiculares: cosseno dá 1; L2 ao quadrado daria 2
    colecao.add(ids=["a", "b"], embeddings=[[1.0, 0.0], [0.0, 1.0]])
    resultado = colecao.query(query_embeddings=[[1.0, 0.0]], n_results=2)
    assert resultado["distances"][0] == pytest.approx([0.0, 1.0], abs=1e-5)


def test_busca_traz_o_mais_parecido_primeiro(colecao):
    embedder = EmbedderFalso(CONFIG_EMB)
    sincronizar(colecao, CHUNKS, embedder, lote=2)
    ranking = buscar(colecao, embedder.codificar_pergunta("linhas de onibus do campus"), top_k=3)
    assert ranking[0]["chunk_id"] == "c3"
    assert [r["colocacao"] for r in ranking] == [1, 2, 3]
    assert ranking[0]["posicao"] == 0  # posição no documento continua disponível
    assert ranking[0]["source_id"] == "EX-001"


def test_metadados_sem_listas():
    meta = metadados(CHUNKS[0])
    assert all(isinstance(v, (str, int, float, bool)) for v in meta.values())
    assert meta["secoes"] == "Labs | c1"
    assert meta["entidades"] == "lab-x"


def test_apagar_colecao(tmp_path):
    cliente = abrir_cliente(tmp_path / "chroma")
    abrir_colecao(cliente, "teste", "cosine")
    assert apagar_colecao(cliente, "teste") is True
    assert apagar_colecao(cliente, "teste") is False
    SharedSystemClient.clear_system_cache()


def test_chunk_id_repetido_e_erro(colecao):
    with pytest.raises(ValueError):
        sincronizar(colecao, [CHUNKS[0], CHUNKS[0]], EmbedderFalso(CONFIG_EMB), lote=2)


def test_manifesto_detecta_troca_de_modelo():
    config = {"embeddings": CONFIG_EMB, "indice": {"distancia": "cosine"}}
    manifesto = esperado_pela_config(config)
    assert incompatibilidades(manifesto, esperado_pela_config(config)) == []
    outra = {"embeddings": dict(CONFIG_EMB, modelo="outro/modelo"), "indice": {"distancia": "cosine"}}
    erros = incompatibilidades(manifesto, esperado_pela_config(outra))
    assert len(erros) == 1 and "embeddings.modelo" in erros[0]


def test_versao_corpus_estavel():
    fontes = [{"source_id": "EX-1", "versao": "v1", "sha256": "a"},
              {"source_id": "EX-2", "versao": "v1", "sha256": "b"}]
    assert versao_corpus(fontes) == versao_corpus(list(reversed(fontes)))
    assert versao_corpus(fontes) != versao_corpus([dict(fontes[0], sha256="c"), fontes[1]])
