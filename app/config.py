from typing import ClassVar, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
from pathlib import Path
from enum import StrEnum, auto
import yaml
import os

ROOT_DIR            = Path(os.environ["APP_ROOT_DIR"])
CONFIG_DIR          = ROOT_DIR / "app" / "config"
DEFAULT_CONFIG_DIR  = CONFIG_DIR / "defaults"

# ---------------------------------------------------------
# 0. Tag Yetkileri
# ---------------------------------------------------------
class PermissionTag(StrEnum):
    RCON = "RCON"
    LOGS = "LOGS"
    START = "START"
    STOP = "STOP"
    RESTART = "RESTART"

# ---------------------------------------------------------
# 1. Pydantic Modelleri (Şemanız)
# ---------------------------------------------------------
class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

class LoggerConfig(BaseModel):
    colored: bool = True

class ApiKeyMeta(BaseModel):
    name: str = "Bilinmeyen İstemci"
    tags: Set[str] = Field(default_factory=set)  # Yetki etiketleri (örn: {"action:start", "rgb:write"})
    is_active: bool = True

    def has_permission(self, tag: str | PermissionTag) -> bool:
        """Yetki denetimi yapan yardımcı metot"""
        return self.is_active and tag in self.tags

class MCRconConfig(BaseModel):
    host: str
    port:int
    timeout: int
    password:str

class MCLogsConfig(BaseModel):
    service_name:str
    line_count:int

class MinecraftServerConfig(BaseModel):
    host:str = "127.0.0.1"
    port:int = 25565
    rcon: MCRconConfig
    logs: MCLogsConfig
    service_name:str


class AppConfig(BaseModel):
    s_instance:ClassVar["AppConfig"] = None

    @classmethod
    def get_instance(cls) -> Optional["AppConfig"]:
        return cls.s_instance

    app_name: str
    version: str = "1.0.0"
    server: ServerConfig
    logger: LoggerConfig
    minecraft: MinecraftServerConfig
    # API key (string) -> ApiKeyMeta nesnesi
    api_keys: Dict[str, ApiKeyMeta] = Field(default_factory=dict)

# ---------------------------------------------------------
# 2. Güvenli Derin Birleştirme (Deep Merge) Fonksiyonu
# ---------------------------------------------------------
def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    İki sözlüğü özyinelemeli (recursive) olarak birleştirir.
    override içindeki değerler base içindekileri ezer.
    """
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

# ---------------------------------------------------------
# 3. Güncellenmiş Config Yükleyici
# ---------------------------------------------------------
def load_config(filename: str) -> AppConfig:
    default_path = DEFAULT_CONFIG_DIR / filename
    custom_path = CONFIG_DIR / filename

    default_data: Dict[str, Any] = {}
    custom_data: Dict[str, Any] = {}

    # Varsayılan konfigürasyonu oku
    if default_path.exists():
        with default_path.open("r", encoding="utf-8") as f:
            default_data = yaml.safe_load(f) or {}
    else:
        print(f"[WARN] [load_config] Default config bulunamadı: {filename}")

    # Kullanıcı / ortam konfigürasyonunu oku
    if custom_path.exists():
        with custom_path.open("r", encoding="utf-8") as f:
            custom_data = yaml.safe_load(f) or {}
    else:
        print(f"[INFO] [load_config] {custom_path} bulunamadı, varsayılanlar kullanılacak.")

    # Sözlükleri güvenli birleştir (custom, default'un üzerine yazar)
    merged_dict = _deep_merge(default_data, custom_data)

    # Sözlüğü Pydantic nesnesine dönüştür ve doğrula
    AppConfig.s_instance = AppConfig.model_validate(merged_dict)
    return AppConfig.s_instance


