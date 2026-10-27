from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.routers.main import protected_router
from app.minecraft.instance import MinecraftInstance
from app.config import AppConfig

MinecraftInstance(AppConfig.get_instance().minecraft)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Uygulama ayağa kalkarken polling döngüsünü başlat
    MinecraftInstance.get_instance().queryManager.start()
    yield
    # Kapanışta arka plan görevlerini temizle
    await MinecraftInstance.get_instance().queryManager.stop()

fastapi = FastAPI(title="Minecraft Query API", lifespan=lifespan)

fastapi.include_router(protected_router)

