"""
config/settings.py
------------------
Centraliza o carregamento e validação de variáveis de ambiente via pydantic-settings.
Interrompe a execução imediatamente caso qualquer chave crítica esteja ausente.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from loguru import logger

# ---------------------------------------------------------------------------
# Tentativa de importar pydantic-settings; fallback para python-dotenv puro.
# ---------------------------------------------------------------------------
try:
    from pydantic import field_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict

    _USE_PYDANTIC = True
except ImportError:  # pragma: no cover
    _USE_PYDANTIC = False


if _USE_PYDANTIC:

    class Settings(BaseSettings):
        """Configurações do bot com validação automática via Pydantic v2."""

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=True,
            extra="ignore",
        )

        # ── Telegram ──────────────────────────────────────────────────────
        TELEGRAM_TOKEN: str
        TELEGRAM_CHAT_ID: str

        # ── Google Sheets ─────────────────────────────────────────────────
        GOOGLE_SHEETS_KEY: str
        GOOGLE_SERVICE_ACCOUNT_JSON: str = "service_account.json"
        SHEETS_WORKSHEET_NAME: str = "Produtos"

        # ── Cloudinary ────────────────────────────────────────────────────
        CLOUDINARY_URL: str  # formato: cloudinary://api_key:api_secret@cloud_name
        CLOUDINARY_FOLDER: str = "esotéricas"

        # ── Shopee API (Oficial) ──────────────────────────────────────────
        SHOPEE_APP_ID: str
        SHOPEE_SECRET_KEY: str

        # ── Shopee / Scraper ───────────────────────────────────────────────
        SHOPEE_SESSION_STORAGE_PATH: Optional[str] = None
        SCRAPER_HEADLESS: bool = True
        SCRAPER_TIMEOUT_MS: int = 30_000

        # ── Controle de fluxo ─────────────────────────────────────────────
        MAX_POSTS_PER_RUN: int = 1  # GitHub Actions: postar 1 produto por trigger
        STATUS_PENDENTE: str = "Pendente"
        STATUS_POSTADO: str = "Postado"
        STATUS_ERRO: str = "Erro"

        # ── Categoria padrão (fallback) ────────────────────────────────────
        CATEGORIA_FALLBACK: str = "outros"

        # ── NLP / Categorização ───────────────────────────────────────────
        TFIDF_MIN_DF: int = 1
        TFIDF_NGRAM_MAX: int = 2
        CATEGORIZATION_CONFIDENCE_THRESHOLD: float = 0.10  # score mínimo aceito

        @field_validator("TELEGRAM_TOKEN")
        @classmethod
        def _check_telegram_token(cls, v: str) -> str:
            if not v or ":" not in v:
                raise ValueError(
                    "TELEGRAM_TOKEN inválido. Formato esperado: '123456:ABC-DEF...'"
                )
            return v

        @field_validator("CLOUDINARY_URL")
        @classmethod
        def _check_cloudinary_url(cls, v: str) -> str:
            if not v.startswith("cloudinary://"):
                raise ValueError(
                    "CLOUDINARY_URL inválida. Formato esperado: 'cloudinary://key:secret@cloud'"
                )
            return v

        @field_validator("GOOGLE_SERVICE_ACCOUNT_JSON")
        @classmethod
        def _check_service_account_file(cls, v: str) -> str:
            path = Path(v)
            if not path.exists():
                raise ValueError(
                    f"Arquivo de Service Account não encontrado: {path.resolve()}"
                )
            return v

    @lru_cache(maxsize=1)
    def get_settings() -> Settings:
        """Retorna instância singleton de Settings, com cache."""
        try:
            cfg = Settings()
            logger.info("✅ Configurações carregadas e validadas com sucesso (pydantic-settings).")
            return cfg
        except Exception as exc:
            logger.critical(f"❌ Falha ao carregar configurações: {exc}")
            sys.exit(1)


else:
    # ── Fallback: python-dotenv puro ──────────────────────────────────────
    import os
    from dotenv import load_dotenv

    load_dotenv()

    _REQUIRED_KEYS = [
        "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID",
        "GOOGLE_SHEETS_KEY",
        "CLOUDINARY_URL",
    ]

    class _SimpleCfg:  # type: ignore[no-redef]
        """Configurações lidas diretamente de os.environ."""

        def __getattr__(self, name: str) -> str:
            val = os.getenv(name)
            if val is None:
                raise AttributeError(f"Variável de ambiente não encontrada: {name}")
            return val

    def get_settings() -> _SimpleCfg:  # type: ignore[return-value]
        missing = [k for k in _REQUIRED_KEYS if not os.getenv(k)]
        if missing:
            logger.critical(f"❌ Variáveis obrigatórias ausentes: {missing}")
            sys.exit(1)
        logger.info("✅ Configurações carregadas via python-dotenv (fallback).")
        return _SimpleCfg()


# ---------------------------------------------------------------------------
# Dicionário central de categorias (taxonomia oficial - 9 categorias)
# ---------------------------------------------------------------------------
CATEGORIAS: dict[str, str] = {
    "tarot_baralhos": "🃏",
    "livros_material_estudo": "📚",
    "acessorios_bijuterias": "📿",
    "ferramentas_rituais": "🪄",
    "vestuário": "👕",
    "imagens_estatuas": "🗿",
    "insumos_ervas_sementes": "🌱",
    "incensos_perfumes": "🌿",
    "outros": "✨",
}

CATEGORIA_FALLBACK_EMOJI = "✨"
CATEGORIA_FALLBACK_KEY = "outros"


def emoji_para_categoria(categoria: str) -> str:
    """Retorna o emoji correspondente à categoria, com fallback seguro."""
    return CATEGORIAS.get(categoria, CATEGORIA_FALLBACK_EMOJI)


# ---------------------------------------------------------------------------
# Nomes das colunas do Google Sheets
# Usados por message_generator.py, sheets_client.py e main.py.
# Centralizar aqui garante que uma renomeação de coluna seja feita em
# um único lugar sem risco de divergência entre módulos.
# ---------------------------------------------------------------------------
COL_GS_NOME       = "Nome"
COL_GS_LINK       = "Link_Afiliado"
COL_GS_PRECO_DE   = "Preco_De"
COL_GS_PRECO_POR  = "Preco_Por"
COL_GS_URL_IMAGEM = "URL_Imagem"
COL_GS_STATUS     = "Status"

CABECALHOS_SHEETS = [
    COL_GS_NOME,
    COL_GS_LINK,
    COL_GS_PRECO_DE,
    COL_GS_PRECO_POR,
    COL_GS_URL_IMAGEM,
    COL_GS_STATUS,
]

STATUS_PENDENTE = "Pendente"
STATUS_POSTADO  = "Postado"
STATUS_ERRO     = "Erro"

# ---------------------------------------------------------------------------
# Scopes do Google — necessários para gspread / sheets_client.py
# ---------------------------------------------------------------------------
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]