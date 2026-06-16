"""
modules/message_generator.py
-----------------------------
Motor de formatação de mensagens para o Telegram.
Suporta HTML (preferido pela estabilidade) e MarkdownV2 como alternativa.
Usa a taxonomia oficial de 9 categorias com emojis fixos.
Trata todos os caracteres especiais do Telegram de forma profissional.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

from config.settings import CATEGORIAS, CATEGORIA_FALLBACK_EMOJI, CATEGORIA_FALLBACK_KEY, emoji_para_categoria

# ──────────────────────────────────────────────────────────────────────────────
# Constantes de Formatação
# ──────────────────────────────────────────────────────────────────────────────

# Todos os caracteres que o Telegram exige escape em MarkdownV2
_MDV2_SPECIAL_CHARS = r"\_*[]()~`>#+-=|{}.!"

# Caracteres que o Telegram HTML não aceita diretamente
_HTML_ESCAPE_TABLE = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
}

# Mapeamento de fallback de categoria → chave canônica
_CATEGORIA_ALIASES: dict[str, str] = {
    "tarot": "tarot_baralhos",
    "baralho": "tarot_baralhos",
    "baralhos": "tarot_baralhos",
    "livro": "livros_material_estudo",
    "livros": "livros_material_estudo",
    "estudo": "livros_material_estudo",
    "bijuteria": "acessorios_bijuterias",
    "bijuterias": "acessorios_bijuterias",
    "acessório": "acessorios_bijuterias",
    "acessorios": "acessorios_bijuterias",
    "ritual": "ferramentas_rituais",
    "ferramenta": "ferramentas_rituais",
    "vela": "ferramentas_rituais",
    "roupa": "vestuário",
    "camiseta": "vestuário",
    "vestuario": "vestuário",
    "imagem": "imagens_estatuas",
    "estatua": "imagens_estatuas",
    "estátua": "imagens_estatuas",
    "erva": "insumos_ervas_sementes",
    "ervas": "insumos_ervas_sementes",
    "semente": "insumos_ervas_sementes",
    "incenso": "incensos_perfumes",
    "perfume": "incensos_perfumes",
    "geral": "outros",
}


# ──────────────────────────────────────────────────────────────────────────────
# Dataclass de produto normalizado
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ProdutoTelegram:
    """Representa um produto já normalizado, pronto para formatação."""

    titulo: str
    preco_por: str
    preco_de: Optional[str] = None
    categoria: str = CATEGORIA_FALLBACK_KEY
    link_afiliado: Optional[str] = None
    url_imagem: Optional[str] = None
    descricao_extra: Optional[str] = None
    row_number: int = 0  # linha na planilha (para callback de status)
    raw: dict[str, Any] = field(default_factory=dict)  # linha bruta do Sheets

    def __post_init__(self) -> None:
        # Normaliza a categoria para uma chave válida
        self.categoria = _normalizar_categoria(self.categoria)

    @property
    def emoji(self) -> str:
        return emoji_para_categoria(self.categoria)

    @property
    def categoria_display(self) -> str:
        return self.categoria.replace("_", " ").title()


def _normalizar_categoria(raw_categoria: str) -> str:
    """
    Normaliza uma string de categoria para uma das 9 chaves canônicas.
    Usa aliases e fallback robusto.
    """
    if not raw_categoria:
        return CATEGORIA_FALLBACK_KEY

    normalized = raw_categoria.strip().lower()

    # Verifica correspondência direta
    if normalized in CATEGORIAS:
        return normalized

    # Verifica via alias
    if normalized in _CATEGORIA_ALIASES:
        return _CATEGORIA_ALIASES[normalized]

    # Verifica correspondência parcial
    for alias, canonical in _CATEGORIA_ALIASES.items():
        if alias in normalized:
            return canonical

    logger.warning(
        f"⚠️  Categoria desconhecida '{raw_categoria}', usando fallback '{CATEGORIA_FALLBACK_KEY}'."
    )
    return CATEGORIA_FALLBACK_KEY


def produto_from_sheets_row(row: dict[str, Any], row_number: int = 0) -> ProdutoTelegram:
    """
    Constrói um ProdutoTelegram a partir de uma linha do Google Sheets.
    Resolve colunas comuns da exportação Shopee + colunas de controle do bot.
    """

    def _get(*keys: str, default: str = "") -> str:
        """Busca o valor da primeira chave encontrada no dict."""
        for key in keys:
            val = row.get(key, "")
            if val and str(val).strip():
                return str(val).strip()
        return default

    titulo = _get("Nome", "Titulo", "nome", "titulo", "Nome do Produto", default="Produto Esotérico")
    preco_por = _get("Preco_Por", "Preço Por", "preco_por", "Preco Por", "Preço", default="Consulte")
    preco_de = _get("Preco_De", "Preço De", "preco_de", "Preco De") or None
    categoria = _get("Categoria", "categoria", default=CATEGORIA_FALLBACK_KEY)
    link_afiliado = _get("Link_Afiliado", "link_afiliado", "Link Afiliado", "URL Afiliado") or None
    url_imagem = _get("URL_Imagem_Cloudinary", "URL_Imagem", "url_imagem", "Imagem") or None
    descricao_extra = _get("Descricao", "Descrição", "descricao") or None

    return ProdutoTelegram(
        titulo=titulo,
        preco_por=_formatar_preco(preco_por),
        preco_de=_formatar_preco(preco_de) if preco_de else None,
        categoria=categoria,
        link_afiliado=link_afiliado,
        url_imagem=url_imagem,
        descricao_extra=descricao_extra,
        row_number=row_number,
        raw=row,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Utilitários de Formatação
# ──────────────────────────────────────────────────────────────────────────────


def _formatar_preco(valor: Optional[str]) -> str:
    """Formata um preço para exibição. Ex: '29.90' → 'R$ 29,90'."""
    if not valor:
        return ""
    try:
        # Remove símbolos e normaliza separadores
        limpo = re.sub(r"[^\d.,]", "", str(valor)).replace(".", "").replace(",", ".")
        numero = float(limpo)
        return f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, AttributeError):
        return str(valor).strip()


def _escape_html(text: str) -> str:
    """Escapa caracteres reservados do HTML para uso no Telegram (modo HTML)."""
    for char, entity in _HTML_ESCAPE_TABLE.items():
        text = text.replace(char, entity)
    return text


def _escape_mdv2(text: str) -> str:
    """Escapa todos os caracteres especiais do MarkdownV2 do Telegram."""
    return re.sub(r"([" + re.escape(_MDV2_SPECIAL_CHARS) + r"])", r"\\\1", text)


# ──────────────────────────────────────────────────────────────────────────────
# Geração de Mensagem Principal (HTML)
# ──────────────────────────────────────────────────────────────────────────────


def gerar_mensagem_html(produto: ProdutoTelegram) -> str:
    """
    Gera o texto da mensagem em formato HTML para o Telegram.
    Inclui: emoji, título, preço (com riscado se houver De/Por), categoria e CTA.
    """
    emoji = produto.emoji
    titulo = _escape_html(produto.titulo)
    categoria_display = _escape_html(produto.categoria_display)

    # ── Bloco de preço ────────────────────────────────────────────────────────
    if produto.preco_de and produto.preco_de != produto.preco_por:
        preco_bloco = (
            f"<s>{_escape_html(produto.preco_de)}</s>  "
            f"<b>{_escape_html(produto.preco_por)}</b>"
        )
    else:
        preco_bloco = f"<b>{_escape_html(produto.preco_por)}</b>"

    # ── Bloco de CTA (Call to Action) ─────────────────────────────────────────
    if produto.link_afiliado:
        link_limpo = produto.link_afiliado.strip()
        cta_bloco = f'\n\n🛒 <a href="{link_limpo}">Ver na Shopee →</a>'
    else:
        cta_bloco = ""

    # ── Bloco de descrição extra (opcional) ───────────────────────────────────
    descricao_bloco = ""
    if produto.descricao_extra:
        desc = _escape_html(produto.descricao_extra[:300])  # limita tamanho
        descricao_bloco = f"\n\n<i>{desc}</i>"

    # ── Montagem final ────────────────────────────────────────────────────────
    mensagem = (
        f"{emoji} <b>{titulo}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 {preco_bloco}\n"
        f"🏷️ #{_escape_html(produto.categoria.replace(' ', '_'))}"
        f"{descricao_bloco}"
        f"{cta_bloco}"
    )

    logger.debug(f"📝 Mensagem HTML gerada ({len(mensagem)} chars).")
    return mensagem


def gerar_mensagem_mdv2(produto: ProdutoTelegram) -> str:
    """
    Gera o texto da mensagem em formato MarkdownV2 para o Telegram.
    Alternativa ao HTML; todos os caracteres especiais são escapados corretamente.
    """
    emoji = produto.emoji
    titulo = _escape_mdv2(produto.titulo)
    categoria_display = _escape_mdv2(produto.categoria_display)

    # ── Bloco de preço ────────────────────────────────────────────────────────
    if produto.preco_de and produto.preco_de != produto.preco_por:
        preco_bloco = (
            f"~{_escape_mdv2(produto.preco_de)}~  "
            f"*{_escape_mdv2(produto.preco_por)}*"
        )
    else:
        preco_bloco = f"*{_escape_mdv2(produto.preco_por)}*"

    # ── CTA ───────────────────────────────────────────────────────────────────
    if produto.link_afiliado:
        link = produto.link_afiliado.strip()
        cta_bloco = f"\n\n🛒 [Ver na Shopee →]({link})"
    else:
        cta_bloco = ""

    mensagem = (
        f"{emoji} *{titulo}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 {preco_bloco}\n"
        f"🏷️ \\#{_escape_mdv2(produto.categoria.replace(' ', '_'))}"
        f"{cta_bloco}"
    )

    logger.debug(f"📝 Mensagem MarkdownV2 gerada ({len(mensagem)} chars).")
    return mensagem


# ──────────────────────────────────────────────────────────────────────────────
# API Pública do Módulo
# ──────────────────────────────────────────────────────────────────────────────


def gerar_mensagem(
    produto: ProdutoTelegram,
    parse_mode: str = "HTML",
) -> str:
    """
    Ponto de entrada principal. Gera a mensagem no formato solicitado.

    Args:
        produto: ProdutoTelegram normalizado.
        parse_mode: 'HTML' (padrão) ou 'MarkdownV2'.

    Returns:
        String formatada pronta para envio via Telegram Bot API.
    """
    if parse_mode.upper() == "HTML":
        return gerar_mensagem_html(produto)
    elif parse_mode.upper() in ("MARKDOWNV2", "MDV2"):
        return gerar_mensagem_mdv2(produto)
    else:
        logger.warning(f"parse_mode '{parse_mode}' desconhecido. Usando HTML.")
        return gerar_mensagem_html(produto)
