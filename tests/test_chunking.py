"""Testes do chunking com contador de tokens FALSO (palavras + 2). Sem baixar nada."""

import pytest

from unb_gama_rag.chunking import ErroChunking, agrupar_secoes, gerar_chunks

EMBEDDINGS = {"modelo": "falso", "revisao": "0", "prefixo_documento": "passage: "}


def conta(texto: str) -> int:
    return len(texto.split()) + 2  # imita os tokens especiais <s> e </s>


def cfg(**campos) -> dict:
    base = {"estrategia": "agrupar_irmaos", "alvo_tokens": 60, "sobreposicao_tokens": 5, "max_tokens": 80}
    base.update(campos)
    return base


FONTE = {
    "source_id": "EX-001", "versao": "2026-01-01", "titulo": "Documento de exemplo",
    "url": "https://exemplo.invalid", "campus": "Gama", "abrangencia": "Gama",
    "data_revisao": "", "validade": "desconhecida", "status": "pendente",
}


def secao(*caminho, palavras=5, n=1):
    return {"caminho": list(caminho), "paragrafos": [" ".join([f"p{i}w{j}" for j in range(palavras)]) for i in range(n)]}


# Estrutura parecida com a do DOC-015: introdução e laboratórios agrupados por categoria.
SECOES = [
    secao("Serviços"),
    secao("Serviços", "Materiais", "Lab A"),
    secao("Serviços", "Materiais", "Lab B"),
    secao("Serviços", "Sistemas", "Lab C"),
    secao("Serviços", "Sistemas", "Lab D"),
]


def gerar(secoes=SECOES, **c):
    return gerar_chunks({"secoes": secoes, "sha256_original": "x"}, FONTE, conta, cfg(**c), EMBEDDINGS)


def test_agrupar_irmaos_junta_por_titulo_pai():
    grupos = agrupar_secoes(SECOES, "agrupar_irmaos")
    assert [[s["caminho"][-1] for s in g] for g in grupos] == [["Serviços"], ["Lab A", "Lab B"], ["Lab C", "Lab D"]]


def test_por_secao_um_grupo_por_secao():
    assert len(agrupar_secoes(SECOES, "por_secao")) == 5


def test_estrategia_desconhecida_e_erro():
    with pytest.raises(ErroChunking):
        agrupar_secoes(SECOES, "outra")


def test_texto_tem_titulo_cabecalho_e_rotulos():
    chunk = gerar()[1]
    linhas = chunk["texto"].split("\n")
    assert linhas[:3] == ["Documento de exemplo", "Serviços > Materiais", "Lab A"]
    assert "Lab B" in linhas
    assert chunk["secoes"] == ["Serviços > Materiais > Lab A", "Serviços > Materiais > Lab B"]


def test_opcao_a_gera_um_chunk_por_secao():
    assert len(gerar(estrategia="por_secao")) == 5
    assert len(gerar()) == 3


def test_grupo_maior_que_alvo_quebra_entre_secoes():
    secoes = [secao("Pai", f"Lab {i}", palavras=20) for i in range(4)]
    chunks = gerar(secoes)
    assert len(chunks) == 2
    assert all(len(c["secoes"]) == 2 for c in chunks)  # nenhuma seção cortada ao meio


def test_secao_longa_e_subdividida_com_sobreposicao_sem_perder_texto():
    longa = secao("Longa", palavras=20, n=6)  # 120 palavras, alvo 60
    chunks = gerar([longa], sobreposicao_tokens=25)
    assert len(chunks) > 1
    assert all(c["tokens"] <= 60 for c in chunks)
    # a segunda parte começa repetindo o último parágrafo inteiro da primeira
    ultimo_paragrafo = chunks[0]["texto"].split("\n")[-1]
    assert chunks[1]["texto"].split("\n")[2] == ultimo_paragrafo
    # todas as palavras do original aparecem em algum chunk
    texto_total = " ".join(c["texto"] for c in chunks)
    assert all(p in texto_total for p in " ".join(longa["paragrafos"]).split())


def test_sobreposicao_nunca_corta_paragrafo_ao_meio():
    # parágrafos de 20 palavras e limite de 5 tokens: não cabe inteiro, então não sobrepõe
    longa = secao("Longa", palavras=20, n=6)
    chunks = gerar([longa], sobreposicao_tokens=5)
    paragrafos = set(longa["paragrafos"])
    for chunk in chunks:
        for linha in chunk["texto"].split("\n")[2:]:
            assert linha in paragrafos  # só parágrafos inteiros, nenhum fragmento
    assert sum(len(c["texto"].split("\n")) - 2 for c in chunks) == 6  # nenhum repetido


def test_frase_gigante_e_dividida_por_palavras():
    gigante = {"caminho": ["X"], "paragrafos": [" ".join(f"w{i}" for i in range(200))]}
    chunks = gerar([gigante])
    assert all(c["tokens"] <= 60 for c in chunks)
    texto_total = " ".join(c["texto"] for c in chunks)
    assert all(f"w{i}" in texto_total.split() for i in range(200))


def test_tokens_incluem_prefixo():
    chunk = gerar()[0]
    assert chunk["tokens"] == conta("passage: " + chunk["texto"])


def test_acima_do_maximo_e_erro():
    # cabeçalho sozinho já passa do máximo: precisa dar erro, não truncar
    with pytest.raises(ErroChunking):
        gerar([secao("t " * 100)], max_tokens=50)


def test_chunk_id_estavel_e_muda_com_config():
    ids = [c["chunk_id"] for c in gerar()]
    assert ids == [c["chunk_id"] for c in gerar()]
    assert len(set(ids)) == len(ids)
    assert ids != [c["chunk_id"] for c in gerar(alvo_tokens=61)]


def test_metadados_da_fonte():
    chunk = gerar()[0]
    assert chunk["source_id"] == "EX-001" and chunk["versao"] == "2026-01-01"
    assert chunk["abrangencia"] == "Gama" and chunk["validade"] == "desconhecida"
    assert chunk["rascunho"] is False
