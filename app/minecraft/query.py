from pydantic import BaseModel, field_validator, Field
from typing import List, Optional
from mcstatus import JavaServer
import asyncio
import logging
import struct
import os

from app.config import MCQueryConfig

logger = logging.getLogger("minecraft.query")

class MinecraftServerStat(BaseModel):
    hostname: str = Field(description="Sunucu MOTD açıklaması")
    version: str = Field(description="Sunucu sürümü")
    numplayers: int = Field(description="Mevcut çevrim içi oyuncu sayısı")
    maxplayers: int = Field(description="Maksimum oyuncu kapasitesi")
    hostport: int = Field(description="Sunucu portu")
    hostip: Optional[str] = Field(
        default=None, description="Sunucu IP/Host bilgisi"
    )
    players: List[str] = Field(
        default_factory=list, description="Aktif oyuncu isimleri"
    )
    favicon: Optional[str] = Field(
        default=None, description="Sunucu ikonu (Base64)"
    )
    ping_ms: Optional[int] = Field(
        default=None, description="Gecikme süresi (ms)"
    )

    @field_validator("numplayers", "maxplayers", "hostport", mode="before")
    @classmethod
    def parse_ints(cls, value):
        if isinstance(value, str):
            return int(value)
        return value


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

    def __init__(self, cfg: MCQueryConfig):
        self.cfg = cfg
        self.session_id = struct.unpack(">i", os.urandom(4))[0] & 0x0F0F0F0F
        
        self._stat_cache: Optional[MinecraftServerStat] = None
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._lock = asyncio.Lock()

    async def _send_and_receive(self, packet: bytes) -> bytes:
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _QueryProtocol(),
            remote_addr=(self.cfg.host, self.cfg.port)
        )
        protocol.future = loop.create_future()
        try:
            transport.sendto(packet)
            return await asyncio.wait_for(protocol.future, timeout=self.cfg.timeout)
        finally:
            transport.close()

    async def _handshake(self) -> int:
        packet = struct.pack(">HBi", 0xFEFD, 0x09, self.session_id)
        data = await self._send_and_receive(packet)
        token_str = data[5:].decode("latin-1").rstrip("\x00")
        logger.debug("Handshake Made with minecraft instance")
        return int(token_str)

    async def fetch_full_stat(self) -> MinecraftServerStat:
        """Sunucuyu mcstatus (TCP Server List Ping) üzerinden asenkron sorgular."""
        async with self._lock:
            # mcstatus ile ana port üzerinden bağlantı kurulur
            server = JavaServer.lookup(f"{self.cfg.host}:{self.cfg.port}")
            status = await server.async_status()

            stats = {
                "hostname": status.motd.to_plain(),
                "version": status.version.name,
                "numplayers": status.players.online,
                "maxplayers": status.players.max,
                "hostport": self.cfg.port,
                "hostip": self.cfg.host,
                "players": [p.name for p in status.players.sample] if status.players.sample else [],
                "favicon": status.icon,
                "ping_ms": round(status.latency) if status.latency else 0
            }

            self._stat_cache = MinecraftServerStat.model_validate(stats)
            return self._stat_cache

    def get_cached_stat(self) -> Optional[MinecraftServerStat]:
        return self._stat_cache

    async def _run_loop(self):
        while self._running:
            try:
                await self.fetch_full_stat()
            except asyncio.TimeoutError:
                logger.warning(f"Query zaman aşımına uğradı ({self.cfg.host}:{self.cfg.port}) - Sunucu UDP yanıtı vermiyor.")
            except Exception as e:
                logger.warning(f"Query polling hatası ({self.cfg.host}:{self.cfg.port}): {e}")
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

