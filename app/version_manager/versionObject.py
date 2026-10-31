
import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger("version.object")

class VersionDataModel(BaseModel):
    version_hash:str
    version_full_file_index:dict[str, str]


def get_relative_flat_file_list(base:Path, target:Path = None) -> list[Path]:
    if target is None:
        target = base

    toReturn = []
    for f in target.iterdir():
        if f.is_dir():
            toReturn.extend(get_relative_flat_file_list(base, f))
        if f.is_file():
            if f.parent == base and f.name == "manifest.json":
                continue
            toReturn.append(f.relative_to(base))
    return toReturn


class VersionObject:
    MANIFEST_FILE = "manifest.json"
    def __init__(self, dir:Path):
        self.dir = dir
        self.data:Optional[VersionDataModel] = None

    async def load(self):
        self.data = await self.parse_manifest_file()
        return self

    def is_valid(self): # self.data doğru parse edilebiliyorsa geçerli bir versiyondur
        return self.data is not None

    def version_name(self):
        return self.dir.name

    async def parse_manifest_file(self) -> Optional[VersionDataModel]:
        try:
            content = await self.get_manifest_content()
            if not content:
                return None
            mDICT = json.loads(content)
            return VersionDataModel.model_validate(mDICT)
        except Exception as e:
            logger.error(f"while loading versionfile: {str(self.get_manifest())} an error occured: {e}")
            return None

    def get_manifest(self) -> Path:
        return self.dir / self.MANIFEST_FILE

    async def get_manifest_content(self) -> Optional[str]:
        mFILE = self.get_manifest()
        if not mFILE.exists():
            return None

        return await asyncio.to_thread(mFILE.read_text, encoding="utf-8")

    def __eq__(self, other:"VersionObject") -> bool:
        return self.dir == other.dir

    async def update_manifest(self):
        await asyncio.to_thread(self._sync_update_manifests)

    async def _sync_update_manifests(self):
        file_list = sorted(get_relative_flat_file_list(self.dir), key=lambda x: str(x))
        file_hash_table = {}

        for file in file_list:
            absolute_path = self.dir / file
            # Python 3.11+ özelliği: Doğrudan dosya objesini vererek buffer'sız C seviyesinde hash alma
            with absolute_path.open("rb") as f:
                file_hash_table[str(file)] = hashlib.file_digest(f, "sha256").hexdigest()

        version_hash = hashlib.sha256(json.dumps(file_hash_table).encode()).hexdigest()

        if self.data and self.data.version_hash == version_hash:
            return
        
        manifest = {
            "version_hash": version_hash,
            "version_full_file_index": file_hash_table
        }

        with self.get_manifest().open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)
            
        # Güncellenmiş manifesti yükle
        mDICT = json.loads(self.get_manifest().read_text(encoding="utf-8"))
        self.data = VersionDataModel.model_validate(mDICT)





