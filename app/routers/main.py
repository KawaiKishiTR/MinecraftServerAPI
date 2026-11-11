from typing import Sequence

from fastapi import APIRouter, Depends, Request
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import AppConfig, ApiKeyMeta, PermissionTag
from app.audit_logging import audit_logger

# 2. Header tanımı (Swagger UI'da Authorize kutusu çıkarır)
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

def verify_api_key_permission(tags: Sequence[PermissionTag] = ()):
    def dependency(request: Request, key:str = Security(api_key_header)) -> ApiKeyMeta:
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Header içinde 'x-api-key' eksik!"
            )

        # Config sözlüğümüzden anahtarı ara
        current_key = AppConfig.get_instance().api_keys.get(key)

        if not current_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz API Anahtarı!"
            )

        # Loglama fonksiyonunu request.state üzerine iliştir
        request.state.log_audit = lambda status_code, extra="": audit_logger.log(
            key_name=current_key.name,
            method=request.method,
            path=request.url.path,
            ip=request.client.host if request.client else "unknown",
            status_code=f"{status_code} {extra}".strip()
        )

        if not current_key.is_active:
            request.state.log_audit("403 FORBIDDEN", "Devre Dışı Anahtar Kullanımı!")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu API Anahtarı devre dışı bırakılmış!"
            )

        for tag in tags:
            if (not current_key.has_permission(tag)):
                request.state.log_audit("403 FORBIDDEN", f"Yetki Dışı Anahtar Kullanımı: {tag} | {current_key.tags}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Erişim engellendi! Bu işlem için {tag} yetkisine sahip olmalısınız"
                )

        return current_key
    return dependency

protected_router = APIRouter(dependencies=[Depends(verify_api_key_permission)])