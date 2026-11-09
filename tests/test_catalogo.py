import pytest

from unb_gama_rag.catalogo import COLUNAS, ler_catalogo, validar_catalogo
from unb_gama_rag.config import carregar_config

REGRAS = carregar_config()["catalogo"]
SHA_EXEMPLO = "a" * 64


def fonte(**campos) -> dict:
    """Linha de EXEMPLO (não é fonte real), pendente e válida por padrão."""
    base = {c: "" for c in COLUNAS}
    base.update(
        source_id="EX-001",
        titulo="Página de exemplo",
        tipo="pagina_web",
        url="https://exemplo.invalid/pagina",
        campus="Gama",
        abrangencia="Gama",
        validade="desconhecida",
        status="pendente",
    )
    base.update(campos)
    return base


def aprovada(**campos) -> dict:
    return fonte(
        status="aprovado",
        data_coleta="2026-11-01",
        data_revisao="2026-11-02",
        revisor="Revisor Exemplo",
        sha256=SHA_EXEMPLO,
        versao="1",
        **campos,
    )


def mensagens(fontes):
    return [p.mensagem for p in validar_catalogo(fontes, REGRAS)]


def test_fonte_pendente_valida_nao_gera_problema():
    assert mensagens([fonte()]) == []


def test_fonte_aprovada_completa_nao_gera_problema():
    assert mensagens([aprovada()]) == []


def test_aprovada_sem_revisao_e_sha_gera_problemas():
    erros = mensagens([fonte(status="aprovado")])
    for campo in ["data_coleta", "data_revisao", "revisor", "sha256", "versao"]:
        assert f"fonte aprovada precisa de '{campo}'" in erros


def test_source_id_duplicado():
    assert "source_id duplicado" in mensagens([fonte(), fonte()])


def test_status_invalido():
    assert any("status 'ok' inválido" in m for m in mensagens([fonte(status="ok")]))


def test_rejeitada_sem_motivo():
    assert "fonte rejeitada precisa de motivo" in mensagens([fonte(status="rejeitado")])
    assert mensagens([fonte(status="rejeitado", motivo="outro campus")]) == []


def test_abrangencia_invalida():
    assert any("abrangência 'Brasil'" in m for m in mensagens([fonte(abrangencia="Brasil")]))


def test_abrangencia_gama_exige_campus_gama():
    assert "abrangência Gama exige campus Gama" in mensagens([fonte(campus="")])
    assert mensagens([fonte(campus="", abrangencia="DF")]) == []


def test_data_fora_do_formato():
    assert any("data_coleta" in m for m in mensagens([fonte(data_coleta="01/11/2026")]))


def test_validade_igual_a_data_de_coleta():
    erros = mensagens([fonte(data_coleta="2026-11-01", validade="2026-11-01")])
    assert any("validade igual à data de coleta" in m for m in erros)


def test_validade_texto_invalido():
    assert any("validade deve ser" in m for m in mensagens([fonte(validade="sem validade")]))


def test_sha256_invalido():
    assert any("sha256" in m for m in mensagens([fonte(sha256="abc")]))


def test_relacao_com_fonte_inexistente():
    erros = mensagens([fonte(relacoes="EX-999")])
    assert any("EX-999" in m for m in erros)
    assert mensagens([fonte(relacoes="EX-002"), fonte(source_id="EX-002")]) == []


def test_url_de_pagina_web_precisa_de_http():
    assert any("http" in m for m in mensagens([fonte(url="fcte.unb.br")]))


def test_ler_catalogo_com_coluna_faltando(tmp_path):
    arquivo = tmp_path / "fontes.csv"
    arquivo.write_text("source_id,titulo\nEX-001,Exemplo\n", encoding="utf-8")
    with pytest.raises(ValueError, match="colunas ausentes"):
        ler_catalogo(arquivo)


def test_ler_catalogo_remove_espacos(tmp_path):
    arquivo = tmp_path / "fontes.csv"
    linha = {c: "" for c in COLUNAS}
    linha.update(source_id=" EX-001 ", status="pendente")
    arquivo.write_text(
        ",".join(COLUNAS) + "\n" + ",".join(linha[c] for c in COLUNAS) + "\n",
        encoding="utf-8",
    )
    fontes = ler_catalogo(arquivo)
    assert fontes[0]["source_id"] == "EX-001"
