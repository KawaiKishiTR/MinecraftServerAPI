from fastapi import APIRouter, Depends
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import AppConfig, ApiKeyMeta, PermissionTag

# 2. Header tanımı (Swagger UI'da Authorize kutusu çıkarır)
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> ApiKeyMeta:
    """
    Tüm endpoint'ler için merkezi anahtar doğrulama fonksiyonu.
    Geçersizse 401 veya 403 döner, geçerliyse anahtarın yetki nesnesini döndürür.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header içinde 'x-api-key' eksik!"
        )

    # Config sözlüğümüzden anahtarı ara
    key_info = AppConfig.get_instance().api_keys.get(api_key)

    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz API Anahtarı!"
        )

    if not key_info.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu API Anahtarı devre dışı bırakılmış!"
        )

    return key_info

def verify_api_key_permission(*tags: PermissionTag):
    def func(current_key:ApiKeyMeta = Depends(verify_api_key)) -> ApiKeyMeta:
        for tag in tags:
            if (not current_key.has_permission(tag)):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Erişim engellendi! Bu işlem için {tag} yetkisine sahip olmalısınız"
                )
        
        return current_key
    return func

protected_router = APIRouter(dependencies=[Depends(verify_api_key)])