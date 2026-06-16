"""
modules/shopee_client.py
------------------------
Cliente oficial para a Shopee Affiliate Open API (GraphQL).

RAIZ DOS ERROS CORRIGIDOS NESTA VERSÃO:
  1. Tipo BigInt → Int
       O schema GraphQL da API de Afiliados Shopee BR usa o scalar 'Int',
       não 'BigInt'. O tipo 'BigInt' simplesmente não existe nesse schema,
       daí o erro 'Unknown type "BigInt"' com código 10010.
       Corrigido: $shopId: Int!, $itemId: Int!

  2. Header Authorization com espaços após vírgulas
       A versão anterior usava:
         "SHA256 Credential=X, Timestamp=Y, Signature=Z"
       O validador de assinatura da Shopee é estrito na ausência de espaços.
       Corrigido: "SHA256 Credential=X,Timestamp=Y,Signature=Z"

  3. Campo offerLink ausente dos nodes
       O campo que retorna o link comissionado é 'offerLink', não 'productLink'.
       'productLink' retorna o link orgânico sem comissão.
       Corrigido: offerLink adicionado ao SELECT da query.

  4. Nome do campo no modelo Pydantic inconsistente com main.py
       main.py acessa metadata.commission_link.
       A versão anterior usava alias='promotion_link', quebrando o acesso direto.
       Corrigido: campo renomeado para commission_link sem alias.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

import httpx
from loguru import logger
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────
# MODELO DE DADOS
# ──────────────────────────────────────────────────────────────────────

class ShopeeProductMetadata(BaseModel):
    """
    Dados validados de um produto retornado pela API de Afiliados da Shopee.

    Campos correspondem diretamente aos acessos em main.py:
      metadata.title
      metadata.price
      metadata.commission_link
      metadata.image_url
    """
    title:           str
    price:           float
    commission_link: str
    image_url:       Optional[str] = None
    shop_id:         int
    item_id:         int


# ──────────────────────────────────────────────────────────────────────
# CLIENTE GRAPHQL
# ──────────────────────────────────────────────────────────────────────

class ShopeeGraphQLClient:
    """
    Interface de comunicação com o endpoint GraphQL da Shopee Affiliates BR.
    """

    def __init__(
        self,
        app_id:     str,
        secret_key: str,
        endpoint:   str = "https://open-api.affiliate.shopee.com.br/graphql",
    ) -> None:
        self.app_id     = app_id.strip()
        self.secret_key = secret_key.strip()
        self.endpoint   = endpoint

    # ── Autenticação ──────────────────────────────────────────────────

    def _gerar_headers(self, payload_str: str, timestamp: int) -> dict[str, str]:
        """
        Gera os headers de autenticação SHA256 para a requisição.

        Formato obrigatório do header (SEM espaços após vírgulas):
          SHA256 Credential=APP_ID,Timestamp=TS,Signature=SIG

        Fórmula da assinatura:
          SHA256( APP_ID + TIMESTAMP + PAYLOAD_JSON + SECRET_KEY )

        O payload_str DEVE ser serializado com separadores compactos
        (',', ':') para que a assinatura calculada aqui bata com o
        que o servidor recalcula ao verificar a requisição.
        """
        raw = f"{self.app_id}{timestamp}{payload_str}{self.secret_key}"
        sig = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        return {
            "Content-Type":  "application/json",
            # CRÍTICO: sem espaços após as vírgulas
            "Authorization": f"SHA256 Credential={self.app_id},Timestamp={timestamp},Signature={sig}",
        }

    # ── Query ─────────────────────────────────────────────────────────

    # ── Método principal ──────────────────────────────────────────────

    @staticmethod
    def _build_query(shop_id: int, item_id: int) -> str:
        """
        Constrói a query GraphQL com os IDs embutidos como literais inline.

        Por que inline e não variáveis tipadas?
          O schema da API BR da Shopee registra Int64 como scalar dos CAMPOS
          (shopId, itemId no resolver), mas NÃO o registra como tipo válido
          para declaração de variáveis de entrada. Isso causa o ciclo:
            - BigInt! → 'Unknown type "BigInt"'   (não existe no schema)
            - Int!    → 'expecting type "Int64"'  (Int32 insuficiente)
            - Int64!  → 'wrong type'              (Int64 não é input type)
          Embutir os valores diretamente elimina a camada de declaração
          de tipos de variáveis, que é onde o gateway rejeita. O servidor
          resolve os campos com seus próprios tipos internos sem validar
          o tipo da variável de entrada.
        """
        return (
            f"{{productOfferV2(shopId:{shop_id},itemId:{item_id})"
            f"{{nodes{{productName price offerLink imageUrl shopId itemId}}}}}}"
        )

    async def get_affiliate_metadata(
        self,
        shop_id: int,
        item_id: int,
        client:  httpx.AsyncClient,
    ) -> Optional[ShopeeProductMetadata]:
        """
        Consulta o endpoint GraphQL e retorna os metadados do produto.

        Args:
            shop_id: ID do vendedor extraído da URL da Shopee.
            item_id: ID do produto extraído da URL da Shopee.
            client:  AsyncClient compartilhado pelo chamador (main.py).

        Returns:
            ShopeeProductMetadata validado, ou None em caso de falha.
        """
        timestamp = int(time.time())

        payload_dict: dict[str, Any] = {
            "query": self._build_query(int(shop_id), int(item_id)),
        }

        # Serialização compacta: obrigatório para que a assinatura bata
        payload_str = json.dumps(payload_dict, separators=(",", ":"))
        headers     = self._gerar_headers(payload_str, timestamp)

        try:
            response = await client.post(
                self.endpoint,
                content=payload_str,    # envia bytes já serializados
                headers=headers,
                timeout=15.0,
            )

            if response.status_code != 200:
                logger.error(
                    f"[Shopee] HTTP {response.status_code}: {response.text[:200]}"
                )
                return None

            data = response.json()

            if "errors" in data:
                logger.error(f"[Shopee] Erro GraphQL: {data['errors']}")
                return None

            nodes = (
                data.get("data", {})
                    .get("productOfferV2", {})
                    .get("nodes", [])
            )

            if not nodes:
                logger.warning(
                    f"[Shopee] API retornou lista vazia para "
                    f"shop={shop_id} item={item_id}"
                )
                return None

            node = nodes[0]

            return ShopeeProductMetadata(
                title           = str(node.get("productName") or "").strip() or "Produto Sem Título",
                price           = float(node.get("price") or 0.0),
                commission_link = str(node.get("offerLink") or ""),
                image_url       = node.get("imageUrl") or None,
                shop_id         = int(node.get("shopId") or shop_id),
                item_id         = int(node.get("itemId") or item_id),
            )

        except httpx.TimeoutException:
            logger.error(f"[Shopee] Timeout ao consultar shop={shop_id} item={item_id}")
            return None
        except httpx.HTTPError as exc:
            logger.error(f"[Shopee] Falha de rede: {exc}")
            return None
        except Exception as exc:
            logger.error(f"[Shopee] Erro inesperado: {exc}")
            return None