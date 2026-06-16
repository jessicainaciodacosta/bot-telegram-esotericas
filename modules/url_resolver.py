import re
from typing import Optional, Tuple
import httpx
from loguru import logger

class URLResolver:
    """Middleware assíncrono para extração e resolução de redirecionamentos de URLs da Shopee."""
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        
        # Lista ordenada de padrões Regex para cobrir todas as variações de URLs conhecidas da Shopee
        self._patterns = [
            # 1. Padrão Desktop/Universal: shopee.com.br/slug-vendedor/shopId/itemId
            # Captura strings numéricas longas após o nome do vendedor/loja
            re.compile(r"shopee\.com\.br/[A-Za-z0-9._-]+/(\d+)/(\d+)"),
            
            # 2. Padrão Rota do Aplicativo: shopee.com.br/product/shopId/itemId
            re.compile(r"product/(\d+)/(\d+)"),
            
            # 3. Padrão Mobile/Compartilhamento: shopee.com.br/...-i.shopId.itemId
            re.compile(r"-i\.(\d+)\.(\d+)")
        ]

    async def resolve_short_url(self, short_url: str, client: httpx.AsyncClient) -> Optional[str]:
        """
        Segue os cabeçalhos de redirecionamento 3xx para capturar a URL final de destino.
        Evita o carregamento de scripts ou scraping visual complexo.
        """
        try:
            logger.info(f"Resolvendo link encurtado: {short_url}")
            # Realiza uma requisição HEAD rápida seguindo os redirecionamentos automaticamente
            response = await client.head(short_url, follow_redirects=True, timeout=self.timeout)
            
            # Fallback para GET caso o servidor da Shopee rejeite ou oculte a location no HEAD
            if response.status_code == 405:
                response = await client.get(short_url, follow_redirects=True, timeout=self.timeout)
                
            final_url = str(response.url)
            logger.debug(f"URL de destino resolvida: {final_url}")
            return final_url
        except httpx.HTTPError as exc:
            logger.error(f"Falha de rede ao resolver a URL {short_url}: {str(exc)}")
            return None

    def extract_shopee_ids(self, url: str) -> Optional[Tuple[int, int]]:
        """
        Aplica múltiplos padrões Regex sobre a URL expandida para extrair o shopId e o itemId.
        Garante a tipagem robusta e a integridade dos dados para a Query GraphQL.
        """
        if not url:
            return None

        # Varre a lista de padrões sequencialmente até encontrar uma correspondência válida
        for pattern in self._patterns:
            match = pattern.search(url)
            if match:
                try:
                    # Como cada Regex é isolada, o grupo 1 é sempre shop_id e o grupo 2 é itemId
                    shop_id = int(match.group(1))
                    item_id = int(match.group(2))
                    return shop_id, item_id
                except (ValueError, IndexError) as exc:
                    logger.error(f"Erro na conversão dos tipos numéricos com o padrão {pattern.pattern}: {exc}")
                    return None

        logger.warning(f"Não foi possível extrair identificadores válidos da URL: {url[:80]}...")
        return None