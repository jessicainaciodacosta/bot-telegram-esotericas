import asyncio
import sys
import httpx
from loguru import logger
from datetime import datetime, timezone

from config.settings import get_settings
from modules.sheets_client import AsyncSheetsClient
from modules.url_resolver import URLResolver
from modules.shopee_client import ShopeeGraphQLClient
from modules.telegram_client import TelegramAsyncClient
from modules.message_generator import ProdutoTelegram, gerar_mensagem

logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}")
logger.add("logs/bot.log", rotation="5 MB", level="DEBUG")


async def processar_oferta_pendente(
    row_data:        dict,
    sheets_client:   AsyncSheetsClient,
    resolver:        URLResolver,
    shopee_client:   ShopeeGraphQLClient,
    telegram_client: TelegramAsyncClient,
    http_client:     httpx.AsyncClient,
) -> bool:
    row_idx = row_data["__row_idx__"]
    raw_url = row_data.get("Product Link")

    if not raw_url:
        logger.warning(f"Linha {row_idx} sem URL na coluna 'Product Link'.")
        await sheets_client.update_cell_value(row_idx, "Status", "Erro: URL Vazia")
        return False

    logger.info(f"🚀 Processando linha {row_idx} | URL: {raw_url}")

    # 1. Resolução do link
    resolved_url = await resolver.resolve_short_url(raw_url, http_client)
    if not resolved_url:
        await sheets_client.update_cell_value(row_idx, "Status", "Erro: Redirecionamento Falhou")
        return False

    # 2. Extração de IDs
    ids = resolver.extract_shopee_ids(resolved_url)
    if not ids:
        logger.error(f"Falha ao extrair ShopID/ItemID de: {resolved_url}")
        await sheets_client.update_cell_value(row_idx, "Status", "Erro: Regex Falhou")
        return False

    shop_id, item_id = ids

    # 3. Consulta à API da Shopee
    metadata = await shopee_client.get_affiliate_metadata(shop_id, item_id, http_client)
    if not metadata:
        await sheets_client.update_cell_value(row_idx, "Status", "Erro: API Shopee Nula")
        return False

    # 4. Monta ProdutoTelegram com o contrato real do message_generator.py
    preco_formatado = f"R$ {metadata.price:.2f}".replace(".", ",")
    categoria = str(row_data.get("categoria") or "outros").strip()

    produto = ProdutoTelegram(
        titulo        = metadata.title,
        preco_por     = preco_formatado,
        link_afiliado = metadata.commission_link,
        url_imagem    = metadata.image_url or row_data.get("URL_Imagem_Cloudinary"),
        categoria     = categoria,
    )

    # 5. Geração do HTML
    mensagem_html = gerar_mensagem(produto, parse_mode="HTML")

    # 6. URL da imagem com fallback
    foto_url = produto.url_imagem or "https://placehold.co/600x400?text=Sem+Imagem"

    # 7. Envio para o Telegram
    sucesso_postagem = await telegram_client.send_offer_card(
        photo_url    = foto_url,
        caption_html = mensagem_html,
        client       = http_client,
    )

    if sucesso_postagem:
        data_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        await sheets_client.update_cell_value(row_idx, "Link_Afiliado", metadata.commission_link)
        await sheets_client.update_cell_value(row_idx, "Status", "Postado")
        logger.success(f"✅ Sucesso total para a linha {row_idx}")
        return True
    else:
        await sheets_client.update_cell_value(row_idx, "Status", "Erro: Envio Telegram Falhou")
        return False


async def main() -> None:
    cfg = get_settings()

    sheets_client   = AsyncSheetsClient()
    resolver        = URLResolver()
    shopee_client   = ShopeeGraphQLClient(app_id=cfg.SHOPEE_APP_ID, secret_key=cfg.SHOPEE_SECRET_KEY)
    telegram_client = TelegramAsyncClient(token=cfg.TELEGRAM_TOKEN, chat_id=cfg.TELEGRAM_CHAT_ID)

    await sheets_client.connect()
    linhas_pendentes = await sheets_client.fetch_pending_rows()

    if not linhas_pendentes:
        logger.info("Nenhum produto pendente para processamento nesta rodada.")
        return

    logger.info(f"📋 Encontradas {len(linhas_pendentes)} ofertas prontas para mineração.")

    max_posts = getattr(cfg, "MAX_POSTS_PER_RUN", 3)
    linhas_a_processar = linhas_pendentes[:max_posts]

    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(limits=limits, verify=True) as http_client:
        for row in linhas_a_processar:
            await processar_oferta_pendente(
                row_data        = row,
                sheets_client   = sheets_client,
                resolver        = resolver,
                shopee_client   = shopee_client,
                telegram_client = telegram_client,
                http_client     = http_client,
            )
            await asyncio.sleep(4.0)


if __name__ == "__main__":
    asyncio.run(main())