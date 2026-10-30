import subprocess
from typing import ClassVar, Optional

from app.config import MinecraftServerConfig
from app.minecraft.logwatcher import SystemctlLogWatcher
from app.minecraft.query import MinecraftQuery
from app.minecraft.rcon import MinecraftRCON


class MinecraftInstance:
    s_instance: ClassVar["MinecraftInstance"] = None
    def __new__(cls, *args, **kwargs):
        cls.s_instance = super().__new__(cls)
        return cls.s_instance

    @classmethod
    def get_instance(cls) -> Optional["MinecraftInstance"]:
        return cls.s_instance

    def __init__(self, cfg: MinecraftServerConfig):
        self.cfg = cfg
        self.logWatcher = SystemctlLogWatcher(cfg.logs)
        self.queryManager = MinecraftQuery(cfg.query)
        self.rcon       = MinecraftRCON(cfg.rcon)

    def get_args(self, action:str):
        return ["sudo", "systemctl", action, self.cfg.service_name]

    def start(self):
        result = subprocess.run(self.get_args("start"), capture_output=True, text=True)

        if (result.returncode == 0):
            return 0
        return 1

    def stop(self):
        result = subprocess.run(self.get_args("stop"), capture_output=True, text=True)

        if (result.returncode == 0):
            return 0
        return 1
        
    def restart(self):
        result = subprocess.run(self.get_args("restart"), capture_output=True, text=True)

        if (result.returncode == 0):
            return 0
        return 1

    def is_service_active(self):
        result = subprocess.run(["sudo", "systemctl", "is-active", self.cfg.service_name], capture_output=True, text=True)

        if (result.returncode == 0):
            return result.stdout == "active"
        return 0