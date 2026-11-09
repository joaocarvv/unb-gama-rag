"""Testes da normalização com entidades de EXEMPLO."""

from unb_gama_rag.config import caminho_projeto, carregar_config
from unb_gama_rag.normalizacao import carregar_entidades, compilar, marcar, validar_entidades

ENTIDADES = [
    {"id": "predio-x", "tipo": "predio", "nome": "Unidade Exemplo",
     "variantes": ["UEX", "Prédio UEX", "Unidade Exemplo"], "fonte": "EX-001"},
    {"id": "lab-y", "tipo": "laboratorio", "nome": "Laboratório Y",
     "variantes": ["LaY", "Laboratório Y"], "fonte": "EX-001"},
]
COMPILADAS = compilar(ENTIDADES)


def test_marca_sigla_e_nome():
    assert marcar("Local: Prédio UEX, sala 2", COMPILADAS) == ["predio-x"]
    assert marcar("na unidade exemplo e no Laboratório Y", COMPILADAS) == ["lab-y", "predio-x"]


def test_sigla_compara_maiusculas_exatamente():
    assert marcar("o uex e o lay", COMPILADAS) == []


def test_nao_marca_pedaco_de_palavra():
    assert marcar("UEXTRA e LaYout e AUEX", COMPILADAS) == []


def test_nao_altera_texto():
    texto = "Local: Prédio UEX"
    marcar(texto, COMPILADAS)
    assert texto == "Local: Prédio UEX"


def test_validacao():
    assert validar_entidades(ENTIDADES, {"EX-001"}) == []
    erros = validar_entidades(ENTIDADES + [dict(ENTIDADES[1], id="lab-z")], {"EX-002"})
    assert any("fonte EX-001 não existe" in e for e in erros)
    assert any("variante 'LaY'" in e for e in erros)


def test_tabela_do_projeto_e_valida():
    config = carregar_config()
    entidades = carregar_entidades(caminho_projeto("config/entidades.yaml"))
    # as fontes citadas precisam existir no catálogo
    from unb_gama_rag.catalogo import ler_catalogo
    ids = {f["source_id"] for f in ler_catalogo(caminho_projeto(config["caminhos"]["catalogo"]))}
    assert validar_entidades(entidades, ids) == []
