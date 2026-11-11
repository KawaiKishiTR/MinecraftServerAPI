from fastapi import APIRouter, Depends, WebSocket
from fastapi import HTTPException, status
from fastapi.requests import HTTPConnection
from fastapi.security import APIKeyHeader

from app.config import AppConfig, ApiKeyMeta, PermissionTag
from app.audit_logging import audit_logger

# 2. Header tanımı (Swagger UI'da Authorize kutusu çıkarır)
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

class ApiKeyPermissionChecker:
    def __init__(self, *tags: PermissionTag):
        self.tags = tags

    async def __call__(self, connection: HTTPConnection) -> ApiKeyMeta:
        key = connection.headers.get("x-api-key")

        if not key:
            await self._reject(connection, status.HTTP_401_UNAUTHORIZED, "Header içinde 'x-api-key' eksik!")

        key_meta = AppConfig.get_instance().api_keys.get(key)
        if not key_meta:
            await self._reject(connection, status.HTTP_401_UNAUTHORIZED, "Geçersiz API Anahtarı!")
        connection.state.log_audit = self._get_log_audit_func(connection, key_meta)

        if not key_meta.is_active:
            self._reject(connection, status.HTTP_403_FORBIDDEN, "Bu API Anahtarı devre dışı bırakılmış!")

        for tag in self.tags:
            if (not key_meta.has_permission(tag)):
                self._reject(connection, status.HTTP_403_FORBIDDEN, f"Yetki Dışı Anahtar Kullanımı: {tag} | {key_meta.tags}")

        return key_meta

    async def _reject(self, connection: HTTPConnection, code:int, detail:str):
        audit_func = getattr(connection.state, "log_audit", None)
        if audit_func is not None:
            audit_func(code, detail)

        if isinstance(connection, WebSocket):
            await connection.close(code=status.WS_1008_POLICY_VIOLATION, reason=detail)
        raise HTTPException(status_code=code, detail=detail)

    def _get_log_audit_func(self, connection: HTTPConnection, key_meta:ApiKeyMeta):
        def log_audit_func(status_code:int, detail:str = ""):
            method_name = getattr(connection, "method", None)
            if method_name is None and isinstance(connection, WebSocket):
                method_name = "WS"
            if method_name is None:
                method_name = "unknown"

            audit_logger.log(
                key_name=key_meta.name,
                method=method_name,
                path=connection.url.path,
                ip=connection.client.host,
                status=f"[{status_code}] {detail}"
            )
        return log_audit_func


protected_router = APIRouter(dependencies=[Depends(ApiKeyPermissionChecker())])