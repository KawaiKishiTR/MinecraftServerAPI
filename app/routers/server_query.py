from typing import Optional
from pydantic import BaseModel

from app.minecraft.instance import MinecraftInstance
from app.minecraft.query import MinecraftServerStat
from app.routers.main import protected_router


def get_stat() -> MinecraftServerStat:
    return MinecraftInstance.get_instance().queryManager.get_cached_stat()

# Tip güvenliği ve otomatik OpenAPI dokümantasyonu için şema tanımı (Data Transfer Object)
class ServerStaticInfo(BaseModel):
    hostname: str
    version: str
    maxplayers: int
    hostip: str
    hostport: int
    favicon: Optional[str] = None

class PlayerInfo(BaseModel):
    numplayers: int
    playerlist: list[str]

# ----------------------------
#  STATIC ENDPOINT (Tek İstek)
# ----------------------------
@protected_router.get("/server/info", response_model=ServerStaticInfo)
async def get_server_info():
    stat = get_stat()
    return {
        "hostname": stat.hostname,
        "version": stat.version,
        "maxplayers": stat.maxplayers,
        "hostip": stat.hostip,
        "hostport": stat.hostport,
        "favicon": stat.favicon,
    }

# ----------------------------
#  DYNAMIC ENDPOINT (Polling İçin)
# ----------------------------
@protected_router.get("/server/playerinfo", response_model=PlayerInfo)
async def get_server_playerinfo():
    stat = get_stat()
    return {
        "numplayers": len(stat.players),
        "playerlist": stat.players
    }







