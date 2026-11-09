"""Testes da extração com HTML pequeno de EXEMPLO (não é página real)."""

import pytest

from unb_gama_rag.config import carregar_config
from unb_gama_rag.extracao import ErroExtracao, extrair_html, regras_para

CONFIG = carregar_config()["extracao"]
REGRAS = regras_para(CONFIG, "exemplo.invalid", "EX-001")

HTML = """
<html><head><title>Página de exemplo</title></head><body>
<header><nav><a href="/">Início</a><a href="/contato">Contato</a></nav></header>
<main>
  <h2>Laboratórios</h2>
  <p>Texto de abertura.</p>
  <h3>Laboratório A</h3>
  <p>O <strong>Laboratório A</strong> fica no <a href="#">prédio X</a>, sala 10.</p>
  <ul><li>Item um</li><li>Item dois</li></ul>
  <h3>Laboratório B</h3>
  <h4>Contato</h4>
  <p>Local: prédio Y</p>
  <p>Local: prédio Y</p>
  <script>var x = 1;</script>
  <form><input value="busca"></form>
</main>
<footer>Rodapé com endereço</footer>
</body></html>
""".encode()


def extrair(html=HTML, regras=REGRAS, min_palavras=1):
    return extrair_html(html, regras, min_palavras)


def test_pega_so_o_conteudo_principal():
    texto = str(extrair()["secoes"])
    assert "Início" not in texto and "Rodapé" not in texto
    assert "var x" not in texto and "busca" not in texto


def test_junta_texto_com_links_e_negrito_na_mesma_linha():
    secao_a = next(s for s in extrair()["secoes"] if s["caminho"][-1] == "Laboratório A")
    assert secao_a["paragrafos"][0] == "O Laboratório A fica no prédio X, sala 10."
    assert secao_a["paragrafos"][1:] == ["Item um", "Item dois"]


def test_secao_guarda_caminho_de_titulos():
    caminhos = [s["caminho"] for s in extrair()["secoes"]]
    assert caminhos == [
        ["Laboratórios"],
        ["Laboratórios", "Laboratório A"],
        ["Laboratórios", "Laboratório B", "Contato"],
    ]


def test_remove_repeticao_consecutiva():
    resultado = extrair()
    assert resultado["secoes"][-1]["paragrafos"] == ["Local: prédio Y"]
    assert resultado["repeticoes_removidas"] == 1


def test_br_quebra_linha_dentro_do_mesmo_paragrafo():
    html = b"""<main><p><strong>Lab C</strong><br>Coordenador: Fulano
      de Tal<br>Local: sala 1</p></main>"""
    paragrafos = extrair(html)["secoes"][0]["paragrafos"]
    assert paragrafos == ["Lab C\nCoordenador: Fulano de Tal\nLocal: sala 1"]


def test_titulo_de_aba_vira_secao():
    html = b"""<main><h2>Labs</h2>
      <div class="elementor-tab-title"><span>Aba 1</span></div><div><p>Conteudo 1</p></div>
      <div class="elementor-tab-title"><span>Aba 2</span></div><div><p>Conteudo 2</p></div></main>"""
    caminhos = [s["caminho"] for s in extrair(html)["secoes"]]
    assert caminhos == [["Labs", "Aba 1"], ["Labs", "Aba 2"]]


def test_titulo_da_pagina():
    assert extrair()["titulo_pagina"] == "Página de exemplo"


def test_area_de_conteudo_ausente_e_erro():
    with pytest.raises(ErroExtracao):
        extrair(b"<html><body><p>sem main</p></body></html>")


def test_avisa_pouco_texto():
    assert any("pouco texto" in a for a in extrair(min_palavras=1000)["avisos"])


def test_regras_por_site_e_por_fonte():
    config = {
        "conteudo_padrao": "main",
        "remover_padrao": ["script"],
        "titulos_extras": [],
        "por_site": {"site.invalid": {"conteudo": "#conteudo", "remover": ["#rodape"]}},
        "por_fonte": {"EX-002": {"remover": [".outro-campus"]}},
    }
    regras = regras_para(config, "site.invalid", "EX-002")
    assert regras["conteudo"] == "#conteudo"
    assert regras["remover"] == ["script", "#rodape", ".outro-campus"]
    assert regras_para(config, "outro.invalid", "EX-001")["conteudo"] == "main"
