from fastapi import Depends, status

from app.config import ApiKeyMeta
from app.routers.main import protected_router, verify_api_key_permission

@protected_router.get("/ping", status_code=status.HTTP_200_OK)
async def ping():
    return

@protected_router.get("/token/get_info", status_code=status.HTTP_200_OK)
async def get_token_permissions(current_token: ApiKeyMeta = Depends(verify_api_key_permission())):
    return {
        "name": current_token.name,
        "tags": list(current_token.tags)
    }

@protected_router.get("/token/exists", status_code=status.HTTP_200_OK)
async def is_token_exists(current_token: ApiKeyMeta = Depends(verify_api_key_permission())):
    return {"exists": True} # doğrulama adımında hata vermediyse zaten vardır
    