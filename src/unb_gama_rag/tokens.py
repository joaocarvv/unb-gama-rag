"""Contagem de tokens com o tokenizer do E5 (só o tokenizer, não o modelo)."""

from tokenizers import Tokenizer


class ContadorTokens:
    """Conta tokens como o E5 vai ver, incluindo os tokens especiais <s> e </s>."""

    def __init__(self, modelo: str, revisao: str):
        self._tokenizer = Tokenizer.from_pretrained(modelo, revision=revisao)
        # O tokenizer do E5 vem configurado para cortar em 512 tokens.
        # Desligamos para a contagem ser real e nada ser truncado em silêncio.
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()

    def __call__(self, texto: str) -> int:
        return len(self._tokenizer.encode(texto).ids)
