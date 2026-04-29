import os
import json
import logging
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Pode ser o JSON inteiro como string (variável de ambiente) ou o caminho do arquivo
_CREDS_ENV  = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")   # JSON como string
_CREDS_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "/app/credentials/service_account.json")
GDRIVE_FOLDER_ID = os.environ["GDRIVE_FOLDER_ID"]  # ID da pasta pública do Drive


def _get_credentials():
    if _CREDS_ENV:
        info = json.loads(_CREDS_ENV)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return service_account.Credentials.from_service_account_file(_CREDS_FILE, scopes=SCOPES)


def upload(file_path: Path) -> str:
    """
    Faz upload do arquivo para o Google Drive.
    Retorna o link público do arquivo.
    """
    creds   = _get_credentials()
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    mime = (
        "application/vnd.ms-excel"
        if file_path.suffix in (".xls", ".xlsx")
        else "text/csv"
    )

    file_metadata = {
        "name": file_path.name,
        "parents": [GDRIVE_FOLDER_ID],
    }
    media = MediaFileUpload(str(file_path), mimetype=mime, resumable=True)

    logger.info(f"Enviando {file_path.name} para o Google Drive...")
    uploaded = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id, webViewLink")
        .execute()
    )

    file_id   = uploaded.get("id")
    view_link = uploaded.get("webViewLink")

    # Torna o arquivo acessível para quem tiver o link
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    logger.info(f"Upload concluído. Link: {view_link}")
    return view_link
