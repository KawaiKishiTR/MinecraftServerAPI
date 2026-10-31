
import logging
from pathlib import Path
from typing import Optional

from app.version_manager.versionObject import VersionObject

logger = logging.getLogger("version.manager")

class VersionManager:
    s_instance:"VersionManager" = None
    def __init__(self, version_folder:Path):
        self.__class__.s_instance = self
        self.vDir = version_folder
        self.vDir.mkdir(exist_ok=True, parents=True)
        self._get_version_list_cache:Optional[list[VersionObject]] = None

    def invalidate_cache(self) -> None:
        self._get_version_list_cache = None

    @classmethod
    def get_instance(cls) -> Optional["VersionManager"]:
        return cls.s_instance

    async def get_version_list(self) -> list[VersionObject]:
        if self._get_version_list_cache is None:
            versions = [await VersionObject(v).load() for v in self.vDir.iterdir() if v.is_dir()]
            self._get_version_list_cache = [v for v in versions if v.is_valid()]
        return self._get_version_list_cache

    async def get_version_dict(self) -> dict[str: VersionObject]:
        return {v.version_name(): v for v in await self.get_version_list()}

    async def update_manifests(self) -> None:
        for version in self.get_version_list():
            await version.update_manifest()

