"""API privada: toda ruta que decida, muestre estado o cambie configuración exige la cabecera X-API-Key.
La clave vive en el servidor (.env); la UI la pide al usuario al abrir, nunca va en el código ni en variables VITE."""
import secrets

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import Config, config

cabecera = APIKeyHeader(name="X-API-Key", auto_error=False)


def exigir_clave(clave: str | None = Security(cabecera), cfg: Config = Depends(config)) -> None:
    if not clave:
        raise HTTPException(status_code=401, detail="falta la cabecera X-API-Key")
    if not secrets.compare_digest(clave.encode(), cfg.api_key.encode()):
        raise HTTPException(status_code=401, detail="clave incorrecta")
