"""Aquisição: baixa cada fonte do catálogo e guarda o original intacto.

O original é a prova do que foi revisado. Nada aqui altera o conteúdo baixado.
Do catálogo, só os campos técnicos (data_coleta, sha256, versao) são preenchidos.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

# Nome do arquivo original por tipo de fonte. PDF entra quando houver fonte PDF.
NOME_ORIGINAL = {"pagina_web": "original.html"}


@dataclass
class Resultado:
    source_id: str
    situacao: str  # baixado, ja_existe, ignorado, erro
    detalhe: str = ""
    avisos: tuple[str, ...] = ()


def sha256_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def pasta_versao(raiz_originais: Path, source_id: str, versao: str) -> Path:
    return Path(raiz_originais) / source_id / versao


class Robots:
    """Consulta o robots.txt de cada site uma vez só e diz se podemos baixar a URL."""

    def __init__(self, cliente: httpx.Client, user_agent: str):
        self.cliente = cliente
        self.user_agent = user_agent
        self._cache: dict[str, RobotFileParser] = {}

    def permite(self, url: str) -> bool:
        partes = urlsplit(url)
        base = f"{partes.scheme}://{partes.netloc}"
        if base not in self._cache:
            parser = RobotFileParser()
            try:
                resposta = self.cliente.get(base + "/robots.txt")
                if resposta.status_code in (401, 403):
                    parser.disallow_all = True
                linhas = resposta.text.splitlines() if resposta.status_code == 200 else []
            except httpx.HTTPError:
                linhas = []  # sem robots.txt acessível, vale a regra padrão: permitido
            parser.parse(linhas)
            self._cache[base] = parser
        return self._cache[base].can_fetch(self.user_agent, url)


def ja_adquirida(fonte: dict, raiz_originais: Path) -> bool:
    versao = fonte["versao"]
    return bool(versao) and (pasta_versao(raiz_originais, fonte["source_id"], versao) / "metadados.json").exists()


def adquirir_fonte(
    fonte: dict,
    cliente: httpx.Client,
    robots: Robots,
    raiz_originais: Path,
    agora: datetime,
    status_ignorados: list[str],
    atualizar: bool = False,
) -> Resultado:
    """Baixa uma fonte, salva original e metadados e preenche os campos técnicos em `fonte`."""
    sid = fonte["source_id"]

    if fonte["status"] in status_ignorados:
        return Resultado(sid, "ignorado", f"status {fonte['status']}")
    if fonte["tipo"] not in NOME_ORIGINAL:
        return Resultado(sid, "ignorado", f"tipo {fonte['tipo']} ainda não suportado")
    if not atualizar and ja_adquirida(fonte, raiz_originais):
        return Resultado(sid, "ja_existe", f"versão {fonte['versao']}")

    url = fonte["url"]
    if not robots.permite(url):
        return Resultado(sid, "erro", "bloqueado pelo robots.txt do site")

    try:
        resposta = cliente.get(url)
    except httpx.HTTPError as erro:
        return Resultado(sid, "erro", f"falha de conexão ({type(erro).__name__})")
    if resposta.status_code != 200:
        return Resultado(sid, "erro", f"HTTP {resposta.status_code}")

    conteudo = resposta.content
    sha = sha256_bytes(conteudo)
    versao = agora.date().isoformat()

    pasta = pasta_versao(raiz_originais, sid, versao)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / NOME_ORIGINAL[fonte["tipo"]]).write_bytes(conteudo)
    metadados = {
        "source_id": sid,
        "versao": versao,
        "url": url,
        "url_final": str(resposta.url),
        "status_http": resposta.status_code,
        "content_type": resposta.headers.get("content-type", ""),
        "coletado_em": agora.isoformat(timespec="seconds"),
        "tamanho_bytes": len(conteudo),
        "sha256": sha,
    }
    (pasta / "metadados.json").write_text(
        json.dumps(metadados, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    avisos = []
    if urlsplit(str(resposta.url)).netloc != urlsplit(url).netloc:
        avisos.append(f"redirecionou para outro site: {resposta.url}")

    tecnicos = {"data_coleta": versao, "sha256": sha, "versao": versao}
    if atualizar or not fonte["sha256"]:
        fonte.update(tecnicos)
    elif fonte["sha256"] != sha:
        avisos.append(
            "SHA diferente do registrado no catálogo: a página mudou ou é outra cópia. "
            "Catálogo mantido; use --atualizar para registrar esta versão"
        )

    return Resultado(sid, "baixado", f"versão {versao}, {len(conteudo)} bytes", tuple(avisos))
