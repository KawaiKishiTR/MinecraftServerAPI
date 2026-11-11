import asyncio
import logging
import socket

from fastapi import Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status

from app.minecraft.rcon import RconPayload
from app.routers.main import protected_router, verify_api_key_permission
from app.config import ApiKeyMeta, PermissionTag
from app.minecraft.instance import MinecraftInstance

@protected_router.post("/minecraft/start", status_code=status.HTTP_200_OK)
async def start(request:Request, current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.START))):
    if MinecraftInstance.get_instance().start():
        request.state.log_audit("500 INTERNAL SERVER ERROR", "Sunucu başlatma işlemi başarısız")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Başlatma işlemi başarısız oldu logları kontrol edin"
        )

    request.state.log_audit("200 OK")
    return {
        "status": "success",
        "message": "Minecraft sunucusu başarıyla başlatıldı",
        "started_by": current_key.name
    }


@protected_router.post("/minecraft/stop", status_code=status.HTTP_200_OK)
async def stop(request:Request, current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.STOP))):
    if MinecraftInstance.get_instance().stop():
        request.state.log_audit("500 INTERNAL SERVER ERROR", "Sunucu durdurma işlemi başarısız")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Durdurma işlemi başarısız oldu logları kontrol edin"
        )

    request.state.log_audit("200 OK")
    return {
        "status": "success",
        "message": "Minecraft sunucusu başarıyla durduruldu",
        "started_by": current_key.name
    }


@protected_router.post("/minecraft/restart", status_code=status.HTTP_200_OK)
async def restart(request:Request, current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.RESTART))):
    if MinecraftInstance.get_instance().restart():
        request.state.log_audit("500 INTERNAL SERVER ERROR", "Sunucu yeniden başlatma işlemi başarısız")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Yeniden Başlatma işlemi başarısız oldu logları kontrol edin"
        )

    request.state.log_audit("200 OK")
    return {
        "status": "success",
        "message": "Minecraft sunucusu başarıyla Yeniden Başlatıldı",
        "started_by": current_key.name
    }


@protected_router.websocket("/minecraft/get_logtail")
async def logs(websocket:WebSocket, current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.LOGS))):
    await websocket.accept()

    instance = MinecraftInstance.get_instance()
    if not instance:
            await websocket.send_text("Minecraft instance henüz başlatılmamış.")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

    watcher = instance.logWatcher
    loop = asyncio.get_running_loop()
    log_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=20)

    # Thread'den gelen logları FastAPI event loop'una güvenle aktaran callback
    def on_new_log(line: str) -> None:
        try:
            loop.call_soon_threadsafe(log_queue.put_nowait, line)
        except asyncio.QueueFull:
            pass
    
    # 1. Tampondaki (buffer) geçmiş logları gönder
    for past_log in watcher.get_logs():
        await websocket.send_text(past_log)

    # 2. Abone ol (İlk abone ise watcher.start() otomatik tetiklenir)
    watcher.subscribe(on_new_log)

    try:
        while True:
            line = await log_queue.get()
            await websocket.send_text(line)
    except (WebSocketDisconnect, ConnectionResetError):
        pass
    except Exception as e:
        logging.error(f"WebSocket log akışında beklenmeyen hata: {e}")
    finally:
        # İstemci koptuğunda abonelikten çıkar (60 sn timer başlar)
        watcher.unsubscribe(on_new_log)

@protected_router.post("/minecraft/send_command")
async def send_rcon_command(request: Request, payload: RconPayload, current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.RCON))):
    clean_command = payload.command.strip()
    if clean_command.startswith("/"):
        clean_command = clean_command[1:]

    try:
        output = MinecraftInstance.get_instance().rcon.execute(clean_command)
        request.state.log_audit("200 OK")
        return {
            "command": clean_command,
            "response": output if output else "Komut calistirildi (Donus yok)."
        }

    except (ConnectionRefusedError, socket.timeout):
        request.state.log_audit("503 SERVICE UNAVAIL", "Rcon bağlanamadı oyun sunucusu kapalı olabilir")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RCON baglantisi saglanamadi veya zaman asimina ugradi. Oyun sunucusu kapali olabilir."
        )
    except PermissionError:
        request.state.log_audit("401 UNAUTHORIZED", "Sunucu Rcon şifresi yanlış")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="RCON sifresi yanlis."
        )
    except Exception as e:
        request.state.log_audit("500 INTERNAL SERVER ERROR", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hata: {str(e)}"
        )

