from fastapi import Depends, status

from app.config import ApiKeyMeta
from app.routers.main import protected_router, verify_api_key

@protected_router.get("/ping", status_code=status.HTTP_200_OK)
async def ping():
    return {"status": "ok"}

@protected_router.get("/get_token_permissions", status_code=status.HTTP_200_OK)
async def get_token_permissions(current_token: ApiKeyMeta = Depends(verify_api_key)):
    return {
        "tags": list(current_token.tags)
    }