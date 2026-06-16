import asyncio
from typing import Dict, Any, Optional
import httpx
from loguru import logger

class TelegramAsyncClient:
    """Gerenciador assíncrono resiliente para envio de mídias e controle de Rate Limiting da API do Telegram."""
    
    def __init__(self, token: str, chat_id: str):
        self.base_url = f"https://api.telegram.org/bot{token}/sendPhoto"
        self.chat_id = chat_id

    async def send_offer_card(self, photo_url: str, caption_html: str, client: httpx.AsyncClient, retries: int = 3) -> bool:
        """
        Dispara um payload estruturado em HTML via método sendPhoto com política de backoff.
        Garante a resiliência em requisições concorrentes ou em lote.
        """
        payload: Dict[str, Any] = {
            "chat_id": self.chat_id,
            "photo": photo_url,
            "caption": caption_html,
            "parse_mode": "HTML"
        }

        backoff_delay = 2.0

        for attempt in range(1, retries + 1):
            try:
                logger.info(f"Enviando card ao canal {self.chat_id} (Tentativa {attempt}/{retries})")
                response = await client.post(self.base_url, json=payload, timeout=20.0)
                
                if response.status_code == 200:
                    logger.success("Card visual publicado no Telegram com sucesso.")
                    return True
                
                # Tratamento de Erro de Rate Limit (HTTP 429)
                if response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", backoff_delay)
                    logger.warning(f"HTTP 429 detectado. Respeitando limite da API. Aguardando {retry_after}s...")
                    await asyncio.sleep(float(retry_after))
                    continue
                
                logger.error(f"Erro na API do Telegram: {response.status_code} - {response.text}")
                
            except httpx.HTTPError as exc:
                logger.error(f"Falha de rede na comunicação com o Telegram: {str(exc)}")
                
            # Incremento de tempo de espera exponencial caso ocorram outros erros intermitentes
            await asyncio.sleep(backoff_delay)
            backoff_delay *= 2

        logger.critical(f"Falha definitiva ao despachar card de oferta após {retries} tentativas.")
        return False