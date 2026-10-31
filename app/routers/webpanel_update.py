from fastapi import Depends, HTTPException, status
from fastapi.responses import FileResponse


from app.config import ApiKeyMeta, PermissionTag
from app.routers.main import protected_router, verify_api_key, verify_api_key_permission
from app.version_manager.versionManager import VersionManager
from app.version_manager.versionObject import VersionObject



@protected_router.get("/version/{version_name}/{file_name:path}", status_code=status.HTTP_200_OK)
async def check_update(version_name:str, file_name:str, current_key: ApiKeyMeta = Depends(verify_api_key)):
    vers:VersionObject = VersionManager.get_instance().get_version_dict().get(version_name)
    if vers is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"versiyon ismi '{version_name} bulunamadı"
        )

    try:
        base_dir = vers.dir.resolve()
        
        safe_file_name = file_name.lstrip("/").lstrip("\\")
        file = (base_dir / safe_file_name).resolve()
        if not file.is_relative_to(base_dir):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="dosya yolunu manipüle edici hareket tespit edildi"
            )
        
    except (ValueError, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz dosya yolu formatı"
        )

    if not file.exists() or not file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"'{version_name}' versiyonuna bağlı '{file_name}' dosyası bulunamadı"
        )

    return FileResponse(file)


@protected_router.post("/version/update_manifests", status_code=status.HTTP_200_OK)
async def update_manifests(current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.ADMIN))):
    await VersionManager.get_instance().update_manifests()

    return {
        "status": "ok"
    }



