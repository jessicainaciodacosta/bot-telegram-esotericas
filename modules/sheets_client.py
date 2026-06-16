import json
from pathlib import Path
from typing import Any, List, Dict, Optional
import gspread_asyncio
from google.oauth2.service_account import Credentials
from loguru import logger
from config.settings import get_settings

class AsyncSheetsClient:
    """Cliente assíncrono resiliente para persistência no Google Sheets."""
    
    def __init__(self):
        self._cfg = get_settings()
        self._agcm = None
        self._worksheet = None
        self._headers: List[str] = []
        self._col_index: Dict[str, int] = {}

    def _get_credentials(self):
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive",
        ]
        # Carrega o arquivo JSON de credenciais mapeado nas configurações
        return Credentials.from_service_account_file(self._cfg.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=scopes)

    async def connect(self) -> None:
        """Estabelece a sessão assíncrona com o Google Sheets API."""
        try:
            self._agcm = gspread_asyncio.AsyncioGspreadClientManager(self._get_credentials)
            agc = await self._agcm.authorize()
            ss = await agc.open_by_key(self._cfg.GOOGLE_SHEETS_KEY)
            self._worksheet = await ss.worksheet(self._cfg.SHEETS_WORKSHEET_NAME)
            
            # Mapeia cabeçalhos para evitar índices mágicos (hardcoded)
            self._headers = await self._worksheet.row_values(1)
            self._col_index = {name: idx + 1 for idx, name in enumerate(self._headers)}
            logger.info("✅ Conexão assíncrona estabelecida com o Google Sheets.")
        except Exception as e:
            logger.critical(f"Falha ao conectar ao Google Sheets: {e}")
            raise e

    async def fetch_pending_rows(self) -> List[Dict[str, Any]]:
        """Busca todas as linhas cujo Status seja 'Pendente'."""
        if self._worksheet is None:
            raise RuntimeError("SheetsClient não inicializado.")
            
        all_records = await self._worksheet.get_all_records()
        pending_records = []
        
        # Preserva o número real da linha física do Sheets (row index é 2-based devido ao cabeçalho)
        for idx, record in enumerate(all_records):
            if str(record.get("Status", "")).strip().lower() == "pendente":
                record["__row_idx__"] = idx + 2
                pending_records.append(record)
                
        logger.info(f"📋 Encontradas {len(pending_records)} ofertas com status 'Pendente'.")
        return pending_records

    async def update_cell_value(self, row: int, column_name: str, value: Any) -> None:
        """Atualiza de forma isolada e atômica uma célula com base no nome da coluna."""
        if self._worksheet is None:
            raise RuntimeError("SheetsClient não inicializado.")
            
        col_idx = self._col_index.get(column_name)
        if not col_idx:
            logger.error(f"Coluna '{column_name}' não existe na planilha.")
            return
            
        await self._worksheet.update_cell(row, col_idx, str(value))
        logger.debug(f"Planilha atualizada: Linha {row}, Coluna {column_name} -> {value}")