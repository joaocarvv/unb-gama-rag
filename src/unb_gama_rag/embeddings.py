"""Embeddings: transforma texto em vetor.

Os prefixos do E5 ("passage: " e "query: ") são colocados só aqui, para nenhum
script esquecer. Os testes usam o EmbedderFalso, que não baixa modelo.
"""

import hashlib
import math
import re


class _Embedder:
    def __init__(self, config_embeddings: dict):
        self.config = config_embeddings
        self.dimensao = config_embeddings["dimensao"]

    def codificar_documentos(self, textos: list[str]) -> list[list[float]]:
        prefixo = self.config["prefixo_documento"]
        return self._codificar([prefixo + t for t in textos])

    def codificar_pergunta(self, texto: str) -> list[float]:
        return self._codificar([self.config["prefixo_pergunta"] + texto])[0]

    def _codificar(self, textos: list[str]) -> list[list[float]]:
        raise NotImplementedError


class EmbedderE5(_Embedder):
    """Modelo E5 real, na revisão fixada no rag.yaml."""

    def __init__(self, config_embeddings: dict):
        super().__init__(config_embeddings)
        # import aqui dentro: quem não usa o modelo (testes, chunking) não carrega o torch
        from sentence_transformers import SentenceTransformer

        self._modelo = SentenceTransformer(
            config_embeddings["modelo"],
            revision=config_embeddings["revisao"],
            device=config_embeddings["dispositivo"],
        )
        dimensao_real = self._modelo.get_sentence_embedding_dimension()
        if dimensao_real != self.dimensao:
            raise ValueError(f"modelo tem {dimensao_real} dimensões, rag.yaml diz {self.dimensao}")
        self._modelo.max_seq_length = config_embeddings["max_tokens"]

    def _codificar(self, textos: list[str]) -> list[list[float]]:
        vetores = self._modelo.encode(
            textos,
            batch_size=self.config["lote"],
            normalize_embeddings=self.config["normalizar"],
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vetores.tolist()


class EmbedderFalso(_Embedder):
    """Para testes. Cada palavra soma 1 numa posição escolhida por hash.

    Textos com palavras em comum ficam próximos, então dá para testar busca
    sem baixar o modelo. Guarda os textos recebidos para conferir os prefixos.
    """

    def __init__(self, config_embeddings: dict):
        super().__init__(config_embeddings)
        self.recebidos: list[str] = []

    def _codificar(self, textos: list[str]) -> list[list[float]]:
        self.recebidos.extend(textos)
        vetores = []
        for texto in textos:
            vetor = [0.0] * self.dimensao
            for palavra in re.findall(r"\w+", texto.lower()):
                indice = int(hashlib.sha256(palavra.encode()).hexdigest(), 16) % self.dimensao
                vetor[indice] += 1.0
            norma = math.sqrt(sum(v * v for v in vetor)) or 1.0
            vetores.append([v / norma for v in vetor])
        return vetores
