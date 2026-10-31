import asyncio
import socket
import subprocess

from fastapi import Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from app.minecraft.query import MinecraftServerStat
from app.minecraft.rcon import RconPayload
from app.routers.main import protected_router, verify_api_key, verify_api_key_permission
from app.config import ApiKeyMeta, PermissionTag
from app.minecraft.instance import MinecraftInstance

@protected_router.post("/action/start", status_code=status.HTTP_200_OK)
async def start(current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.START))):
    if MinecraftInstance.get_instance().start():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Başlatma işlemi başarısız oldu logları kontrol edin"
        )
    
    return {
        "status": "success",
        "message": "Minecraft sunucusu başarıyla başlatıldı",
        "started_by": current_key.name
    }


@protected_router.post("/action/stop", status_code=status.HTTP_200_OK)
async def stop(current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.STOP))):
    if MinecraftInstance.get_instance().stop():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Durdurma işlemi başarısız oldu logları kontrol edin"
        )
    
    return {
        "status": "success",
        "message": "Minecraft sunucusu başarıyla durduruldu",
        "started_by": current_key.name
    }


@protected_router.post("/action/restart", status_code=status.HTTP_200_OK)
async def restart(current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.RESTART))):
    if MinecraftInstance.get_instance().restart():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Yeniden Başlatma işlemi başarısız oldu logları kontrol edin"
        )
    
    return {
        "status": "success",
        "message": "Minecraft sunucusu başarıyla Yeniden Başlatıldı",
        "started_by": current_key.name
    }


@protected_router.websocket("/action/get_logtail")
async def logs(websocket:WebSocket, current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.LOGS))):
    await websocket.accept()

    instance = MinecraftInstance.get_instance()
    if not instance:
            await websocket.send_text("Minecraft instance henüz başlatılmamış.")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

    watcher = instance.logWatcher
    loop = asyncio.get_running_loop()
    log_queue: asyncio.Queue[str] = asyncio.Queue()

    # Thread'den gelen logları FastAPI event loop'una güvenle aktaran callback
    def on_new_log(line: str) -> None:
        loop.call_soon_threadsafe(log_queue.put_nowait, line)

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
    finally:
        # İstemci koptuğunda abonelikten çıkar (60 sn timer başlar)
        watcher.unsubscribe(on_new_log)

# ----------------------------------------------------
# GERİYE DÖNÜK UYUMLULUK FONKSİYONU VAKTİ GELİNCE SİL
##TODO:-----------------------------------------------
@protected_router.get("/status")
async def get_server_status(current_key: ApiKeyMeta = Depends(verify_api_key)):
    if (MinecraftInstance.get_instance().is_service_active()):
        return {
            "status": "success",
            "message": "Minecraft sunucusu Aktif",
            "started_by": current_key.name
        }

    return {
        "status": "success",
        "message": "Minecraft sunucusu Kapalı",
        "started_by": current_key.name
    }

# ----------------------------------------------------
# GERİYE DÖNÜK UYUMLULUK FONKSİYONU VAKTİ GELİNCE SİL
##TODO:-----------------------------------------------
@protected_router.get("/logs")
async def get_server_logs(lines: int = 50, current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.LOGS))):
    cmd = ["sudo", "journalctl", "-u", MinecraftInstance.get_instance().cfg.service_name, "-n", str(lines), "--no-pager"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        return f"Loglar alinirken hata olustu: {result.stderr.strip()}"

    return result.stdout

@protected_router.post("/command")
async def send_rcon_command(payload: RconPayload, current_key: ApiKeyMeta = Depends(verify_api_key_permission(PermissionTag.RCON))):
    clean_command = payload.command.strip()
    if clean_command.startswith("/"):
        clean_command = clean_command[1:]

    try:
        output = MinecraftInstance.get_instance().rcon.execute(clean_command)
        return {
            "command": clean_command,
            "response": output if output else "Komut calistirildi (Donus yok)."
        }

    except (ConnectionRefusedError, socket.timeout):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RCON baglantisi saglanamadi veya zaman asimina ugradi. Oyun sunucusu kapali olabilir."
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="RCON sifresi yanlis."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hata: {str(e)}"
        )


@protected_router.get("/action/get_query_data",
    response_model=MinecraftServerStat, summary="Sunucu durumunu döner")
async def get_server_status(
        fresh:bool = Query(
            default=False,
            description="True verilirse cache atlanır ve anlık UDP sorgusu yapılır.")
        ):
    if fresh:
        try:
            return await MinecraftInstance.get_instance().queryManager.fetch_full_stat()
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Minecraft sunucusundan query yanıtı alınamadı (Zaman aşımı)."
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Sorgulama hatası: {str(e)}"
            )

    cached = MinecraftInstance.get_instance().queryManager.get_cached_stat()
    if cached is None:
        # Cache henüz dolmamışsa ilk veriyi çekmeyi dene
        try:
            return await MinecraftInstance.get_instance().queryManager.fetch_full_stat()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sunucu istatistikleri henüz hazır değil."
            )
    return cached