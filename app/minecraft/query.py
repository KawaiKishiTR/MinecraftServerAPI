from pydantic import BaseModel, field_validator
from typing import List, Optional
from dataclasses import Field
import asyncio
import logging
import struct
import os



class PluginInfo(BaseModel):
    name: str
    version: Optional[str] = None

class MinecraftServerStat(BaseModel):
    hostname: str = Field(description="Sunucu MOTD açıklaması")
    gametype: str = Field(description="Oyun tipi (örn. SMP)")
    game_id: str = Field(description="Oyun kimliği (örn. MINECRAFT)")
    version: str = Field(description="Sunucu sürümü")
    server_engine: Optional[str] = Field(
        default=None, description="Sunucu yazılımı (Paper, Spigot vb.)"
    )
    plugins: List[PluginInfo] = Field(
        default_factory=list, description="Yüklü eklentiler"
    )
    map: str = Field(description="Varsayılan dünya/harita adı")
    numplayers: int = Field(description="Mevcut çevrim içi oyuncu sayısı")
    maxplayers: int = Field(description="Maksimum oyuncu kapasitesi")
    hostport: int = Field(description="Sunucu portu")
    hostip: Optional[str] = Field(
        default=None, description="Sunucu IP/Host bilgisi"
    )
    players: List[str] = Field(
        default_factory=list, description="Aktif oyuncu isimleri"
    )

    # String gelen sayısal alanları int'e çevirme
    @field_validator("numplayers", "maxplayers", "hostport", mode="before")
    @classmethod
    def parse_ints(cls, value):
        if isinstance(value, str):
            return int(value)
        return value

    # "ServerName: Plugin1 1.0; Plugin2 2.0" formatındaki plugins alanını ayrıştırma
    @field_validator("plugins", mode="before")
    @classmethod
    def parse_plugins(cls, value, info):
        if not value or not isinstance(value, str):
            return []

        parsed_plugins = []
        # Query formatı: "Engine: PluginA 1.0; PluginB 2.0"
        if ":" in value:
            engine_part, plugins_part = value.split(":", 1)
            # Dilerseniz engine_part bilgisini server_engine alanına da yazabilirsiniz
            raw_plugins = plugins_part.split(";")
        else:
            raw_plugins = value.split(";")

        for p in raw_plugins:
            p = p.strip()
            if not p:
                continue
            parts = p.split(" ", 1)
            name = parts[0]
            ver = parts[1] if len(parts) > 1 else None
            parsed_plugins.append(PluginInfo(name=name, version=ver))

        return parsed_plugins


logger = logging.getLogger("minecraft.query")

class _QueryProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.future: Optional[asyncio.Future] = None

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]):
        if self.future and not self.future.done():
            self.future.set_result(data)

    def error_received(self, exc: Exception):
        if self.future and not self.future.done():
            self.future.set_exception(exc)


class MinecraftQuery:
    FETCH_INTERVAL: int = 15

    def __init__(self, host: str, port: int = 25565, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.session_id = struct.unpack(">i", os.urandom(4))[0] & 0x0F0F0F0F
        
        self._stat_cache: Optional[MinecraftServerStat] = None
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._lock = asyncio.Lock()

    async def _send_and_receive(self, packet: bytes) -> bytes:
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _QueryProtocol(),
            remote_addr=(self.host, self.port)
        )
        protocol.future = loop.create_future()
        try:
            transport.sendto(packet)
            return await asyncio.wait_for(protocol.future, timeout=self.timeout)
        finally:
            transport.close()

    async def _handshake(self) -> int:
        packet = struct.pack(">HBi", 0xFEFD, 0x09, self.session_id)
        data = await self._send_and_receive(packet)
        token_str = data[5:].decode("latin-1").rstrip("\x00")
        return int(token_str)

    async def fetch_full_stat(self) -> MinecraftServerStat:
        """Sunucuyu doğrudan UDP üzerinden asenkron sorgular."""
        async with self._lock:
            token = await self._handshake()

            packet = (
                struct.pack(">HBi", 0xFEFD, 0x00, self.session_id)
                + struct.pack(">i", token)
                + b"\x00\x00\x00\x00"
            )
            data = await self._send_and_receive(packet)

            body = data[16:]
            kv_section, players_section = body.split(b"\x00\x00\x01player_\x00\x00")

            kv_tokens = kv_section.decode("utf-8", errors="ignore").split("\x00")
            stats = {}
            for i in range(0, len(kv_tokens) - 1, 2):
                key = kv_tokens[i]
                val = kv_tokens[i + 1]
                if key:
                    stats[key] = val

            player_tokens = players_section.decode("utf-8", errors="ignore").split("\x00")
            stats["players"] = [p for p in player_tokens if p]

            self._stat_cache = MinecraftServerStat.model_validate(stats)
            return self._stat_cache

    def get_cached_stat(self) -> Optional[MinecraftServerStat]:
        return self._stat_cache

    async def _run_loop(self):
        while self._running:
            try:
                await self.fetch_full_stat()
            except Exception as e:
                logger.warning(f"Query polling hatası ({self.host}:{self.port}): {e}")
            await asyncio.sleep(self.FETCH_INTERVAL)

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        if self._running:
            self._running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                self._task = None

