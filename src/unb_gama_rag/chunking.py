"""Chunking: corta os documentos extraídos em trechos para a busca.

Regras (CLAUDE.md):
- Respeita título, seção e parágrafo. Nunca mistura documentos no mesmo chunk.
- Estratégia "agrupar_irmaos" (opção C): seções vizinhas com o mesmo título-pai
  vão juntas até o alvo de tokens. "por_secao" (opção A): uma seção por chunk.
- Seção maior que o alvo é subdividida por parágrafo (e por frase, se preciso),
  com sobreposição de até ~40 tokens só nesse caso, feita de unidades inteiras.
- Tokens contados com prefixo e título. Nada passa do máximo: se passar, é erro.
- chunk_id estável: hash de source_id + versão + seções + posição + config.
"""

import hashlib
import json
import re
from typing import Callable

ContaTokens = Callable[[str], int]
SEPARADOR = " > "
ESTRATEGIAS = ("agrupar_irmaos", "por_secao")


class ErroChunking(Exception):
    pass


def _hash(dados) -> str:
    return hashlib.sha256(json.dumps(dados, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def id_config(chunking: dict, embeddings: dict) -> str:
    """Identifica a configuração de chunking. Mudou algo aqui, mudam os chunk_id."""
    return _hash({
        "estrategia": chunking["estrategia"],
        "alvo_tokens": chunking["alvo_tokens"],
        "sobreposicao_tokens": chunking["sobreposicao_tokens"],
        "max_tokens": chunking["max_tokens"],
        "prefixo": embeddings["prefixo_documento"],
        "tokenizer": [embeddings["modelo"], embeddings["revisao"]],
    })[:12]


def agrupar_secoes(secoes: list[dict], estrategia: str) -> list[list[dict]]:
    if estrategia not in ESTRATEGIAS:
        raise ErroChunking(f"estratégia '{estrategia}' desconhecida (use {ESTRATEGIAS})")
    if estrategia == "por_secao":
        return [[secao] for secao in secoes]

    grupos: list[list[dict]] = []
    chave_atual = None
    for secao in secoes:
        chave = tuple(secao["caminho"][:-1])  # título-pai
        if grupos and chave == chave_atual:
            grupos[-1].append(secao)
        else:
            grupos.append([secao])
            chave_atual = chave
    return grupos


def montar_texto(titulo: str, cabecalho: list[str], blocos: list[tuple]) -> str:
    """Texto do chunk: título do documento, título-pai e, para cada seção, rótulo e parágrafos."""
    linhas = [titulo]
    if cabecalho:
        linhas.append(SEPARADOR.join(cabecalho))
    for rotulo, paragrafos, _ in blocos:
        if rotulo:
            linhas.append(rotulo)
        linhas.extend(paragrafos)
    return "\n".join(linhas)


class _Cortador:
    def __init__(self, titulo: str, cabecalho: list[str], conta: ContaTokens, prefixo: str, cfg: dict):
        self.titulo = titulo
        self.cabecalho = cabecalho
        self.conta = conta
        self.prefixo = prefixo
        self.alvo = cfg["alvo_tokens"]
        self.sobreposicao = cfg["sobreposicao_tokens"]

    def medir(self, blocos: list[tuple]) -> int:
        return self.conta(self.prefixo + montar_texto(self.titulo, self.cabecalho, blocos))

    def cabe(self, blocos: list[tuple]) -> bool:
        return self.medir(blocos) <= self.alvo

    def agrupar(self, grupo: list[dict]) -> list[list[tuple]]:
        """Junta seções inteiras até o alvo. Seção que sozinha não cabe é subdividida."""
        pedacos: list[list[tuple]] = []
        atual: list[tuple] = []
        for secao in grupo:
            rotulo = secao["caminho"][-1] if secao["caminho"] else None
            bloco = (rotulo, secao["paragrafos"], SEPARADOR.join(secao["caminho"]))
            if self.cabe(atual + [bloco]):
                atual.append(bloco)
                continue
            if atual:
                pedacos.append(atual)
                atual = []
            if self.cabe([bloco]):
                atual = [bloco]
            else:
                pedacos.extend([[b] for b in self.subdividir(bloco)])
        if atual:
            pedacos.append(atual)
        return pedacos

    def subdividir(self, bloco: tuple) -> list[tuple]:
        """Divide uma seção longa em partes até o alvo, com sobreposição entre elas."""
        rotulo, paragrafos, caminho = bloco

        def cabe_unidades(unidades):
            return self.cabe([(rotulo, unidades, caminho)])

        unidades: list[str] = []
        for paragrafo in paragrafos:
            if cabe_unidades([paragrafo]):
                unidades.append(paragrafo)
                continue
            for frase in re.split(r"(?<=[.!?;])\s+|\n", paragrafo):
                if not frase:
                    continue
                if cabe_unidades([frase]):
                    unidades.append(frase)
                else:
                    unidades.extend(self._quebrar_por_palavras(frase, cabe_unidades))

        partes: list[list[str]] = []
        atual: list[str] = []
        for unidade in unidades:
            if atual and not cabe_unidades(atual + [unidade]):
                partes.append(atual)
                atual = self._sobreposicao(atual)
                if atual and not cabe_unidades(atual + [unidade]):
                    atual = []
            atual.append(unidade)
        if atual:
            partes.append(atual)
        return [(rotulo, parte, caminho) for parte in partes]

    def _sobreposicao(self, unidades: list[str]) -> list[str]:
        """Últimas unidades INTEIRAS (parágrafo ou frase) do pedaço anterior, até o limite.

        Nunca corta uma unidade ao meio: um pedaço de bloco sem o nome do que descreve
        (ex.: a sala de um laboratório sem o nome dele) induziria a erro.
        Se a última unidade inteira não couber, não há sobreposição.
        """
        escolhidas: list[str] = []
        for unidade in reversed(unidades):
            # desconta os 2 tokens especiais <s> e </s>
            if self.conta(" ".join([unidade] + escolhidas)) - 2 > self.sobreposicao:
                break
            escolhidas.insert(0, unidade)
        return escolhidas

    @staticmethod
    def _quebrar_por_palavras(frase: str, cabe) -> list[str]:
        """Último recurso para frase gigante: divide por palavras, sem perder nenhuma."""
        partes, atual = [], []
        for palavra in frase.split():
            if atual and not cabe([" ".join(atual + [palavra])]):
                partes.append(" ".join(atual))
                atual = []
            atual.append(palavra)
        if atual:
            partes.append(" ".join(atual))
        return partes


def gerar_chunks(
    documento: dict,
    fonte: dict,
    conta: ContaTokens,
    chunking: dict,
    embeddings: dict,
    rascunho: bool = False,
) -> list[dict]:
    """Gera os chunks de um documento extraído, com os metadados da fonte."""
    prefixo = embeddings["prefixo_documento"]
    config_id = id_config(chunking, embeddings)
    titulo = fonte["titulo"]

    pedacos: list[tuple[str, list[str]]] = []
    for grupo in agrupar_secoes(documento["secoes"], chunking["estrategia"]):
        cortador = _Cortador(titulo, grupo[0]["caminho"][:-1], conta, prefixo, chunking)
        for blocos in cortador.agrupar(grupo):
            texto = montar_texto(titulo, cortador.cabecalho, blocos)
            secoes = list(dict.fromkeys(b[2] for b in blocos))
            pedacos.append((texto, secoes))

    chunks = []
    for posicao, (texto, secoes) in enumerate(pedacos):
        tokens = conta(prefixo + texto)
        if tokens > chunking["max_tokens"]:
            raise ErroChunking(
                f"{fonte['source_id']} posição {posicao}: {tokens} tokens, acima do máximo "
                f"{chunking['max_tokens']}"
            )
        chunk_id = "c_" + _hash([fonte["source_id"], fonte["versao"], secoes, posicao, config_id])[:16]
        chunks.append({
            "chunk_id": chunk_id,
            "source_id": fonte["source_id"],
            "versao": fonte["versao"],
            "sha256_original": documento["sha256_original"],
            "titulo": titulo,
            "url": fonte["url"],
            "secoes": secoes,
            "posicao": posicao,
            "texto": texto,
            "tokens": tokens,
            "campus": fonte["campus"],
            "abrangencia": fonte["abrangencia"],
            "data_revisao": fonte["data_revisao"],
            "validade": fonte["validade"],
            "status": fonte["status"],
            "rascunho": rascunho,
            "config_chunking": config_id,
        })
    return chunks
