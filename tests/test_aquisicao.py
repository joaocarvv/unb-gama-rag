"""Testes da aquisição com servidor HTTP falso (httpx.MockTransport). Sem rede."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from unb_gama_rag.aquisicao import Robots, adquirir_fonte, sha256_bytes
from unb_gama_rag.catalogo import COLUNAS, ler_catalogo, salvar_catalogo

HTML_EXEMPLO = "<html><body><main><h1>Página de exemplo</h1></main></body></html>".encode()
AGORA = datetime(2026, 11, 9, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
UA = "teste/0.1"


def fonte(**campos) -> dict:
    base = {c: "" for c in COLUNAS}
    base.update(
        source_id="EX-001", titulo="Exemplo", tipo="pagina_web",
        url="https://exemplo.invalid/pagina", campus="Gama", abrangencia="Gama",
        validade="desconhecida", status="pendente",
    )
    base.update(campos)
    return base


def cliente_falso(robots_txt="", status_pagina=200):
    def responder(requisicao: httpx.Request) -> httpx.Response:
        if requisicao.url.path == "/robots.txt":
            return httpx.Response(200, text=robots_txt) if robots_txt else httpx.Response(404)
        return httpx.Response(status_pagina, content=HTML_EXEMPLO, headers={"content-type": "text/html"})

    return httpx.Client(transport=httpx.MockTransport(responder))


def adquirir(f, tmp_path, cliente=None, atualizar=False):
    cliente = cliente or cliente_falso()
    return adquirir_fonte(f, cliente, Robots(cliente, UA), tmp_path, AGORA, ["rejeitado"], atualizar)


def test_baixa_salva_original_e_metadados(tmp_path):
    f = fonte()
    resultado = adquirir(f, tmp_path)

    assert resultado.situacao == "baixado"
    pasta = tmp_path / "EX-001" / "2026-11-09"
    assert (pasta / "original.html").read_bytes() == HTML_EXEMPLO
    metadados = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    assert metadados["sha256"] == sha256_bytes(HTML_EXEMPLO)
    assert metadados["status_http"] == 200


def test_preenche_so_campos_tecnicos(tmp_path):
    f = fonte()
    adquirir(f, tmp_path)
    assert f["sha256"] == sha256_bytes(HTML_EXEMPLO)
    assert f["data_coleta"] == f["versao"] == "2026-11-09"
    assert f["status"] == "pendente"
    assert f["revisor"] == "" and f["validade"] == "desconhecida"


def test_nao_baixa_de_novo_se_ja_existe(tmp_path):
    f = fonte()
    adquirir(f, tmp_path)
    assert adquirir(f, tmp_path).situacao == "ja_existe"


def test_sha_diferente_avisa_e_nao_altera_catalogo(tmp_path):
    f = fonte(sha256="b" * 64, data_coleta="2026-10-01", versao="2026-10-01")
    resultado = adquirir(f, tmp_path)
    assert resultado.situacao == "baixado"
    assert any("SHA diferente" in a for a in resultado.avisos)
    assert f["sha256"] == "b" * 64 and f["versao"] == "2026-10-01"


def test_atualizar_registra_nova_versao(tmp_path):
    f = fonte(sha256="b" * 64, data_coleta="2026-10-01", versao="2026-10-01")
    adquirir(f, tmp_path, atualizar=True)
    assert f["sha256"] == sha256_bytes(HTML_EXEMPLO) and f["versao"] == "2026-11-09"


def test_rejeitada_e_ignorada(tmp_path):
    assert adquirir(fonte(status="rejeitado", motivo="x"), tmp_path).situacao == "ignorado"
    assert not (tmp_path / "EX-001").exists()


def test_tipo_nao_suportado_e_ignorado(tmp_path):
    assert adquirir(fonte(tipo="pdf"), tmp_path).situacao == "ignorado"


def test_erro_http_nao_salva_nada(tmp_path):
    f = fonte()
    resultado = adquirir(f, tmp_path, cliente_falso(status_pagina=404))
    assert resultado.situacao == "erro" and "404" in resultado.detalhe
    assert not (tmp_path / "EX-001").exists()
    assert f["sha256"] == ""


def test_respeita_robots_txt(tmp_path):
    cliente = cliente_falso(robots_txt="User-agent: *\nDisallow: /pagina\n")
    resultado = adquirir(fonte(), tmp_path, cliente)
    assert resultado.situacao == "erro" and "robots" in resultado.detalhe


def test_salvar_catalogo_sem_mudancas_mantem_arquivo_igual(tmp_path):
    arquivo = tmp_path / "fontes.csv"
    conteudo = (
        ",".join(COLUNAS) + "\n"
        + 'EX-001,"Título, com vírgula",pagina_web,https://exemplo.invalid,Gama,Gama,'
        + '"Diz ""olá""",,,desconhecida,,pendente,,,,,,\n'
    )
    arquivo.write_text(conteudo, encoding="utf-8")
    salvar_catalogo(arquivo, ler_catalogo(arquivo))
    assert arquivo.read_text(encoding="utf-8") == conteudo
