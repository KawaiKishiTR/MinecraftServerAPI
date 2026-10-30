from pydantic import BaseModel
import socket
import struct

from app.config import MCRconConfig

class RconPayload(BaseModel):
    command:str

class MinecraftRCON:
    SERVERDATA_AUTH = 3
    SERVERDATA_EXECCOMMAND = 2
    SERVERDATA_RESPONSE_VALUE = 0
    SERVERDATA_AUTH_RESPONSE = 2

    def __init__(self, cfg: MCRconConfig):
        self.cfg = cfg
        self._sock = None

    def _send_packet(self, req_id: int, p_type: int, payload: str):
        encoded_payload = payload.encode('utf-8')
        length = 4 + 4 + len(encoded_payload) + 2  # id (4) + type (4) + body + null padding (2)
        packet = struct.pack(f"<iii{len(encoded_payload)}s2s", length, req_id, p_type, encoded_payload, b"\x00\x00")
        self._sock.sendall(packet)

    def _read_packet(self):
        length_bytes = self._sock.recv(4)
        if not length_bytes or len(length_bytes) < 4:
            raise ConnectionError("RCON sunucusundan eksik veri alindi.")
        
        length = struct.unpack("<i", length_bytes)[0]
        data = b""
        while len(data) < length:
            chunk = self._sock.recv(length - len(data))
            if not chunk:
                raise ConnectionError("Soket baglantisi beklenmedik sekilde kapandi.")
            data += chunk

        req_id, p_type = struct.unpack("<ii", data[:8])
        body = data[8:-2].decode('utf-8', errors='replace')
        return req_id, p_type, body

    def execute(self, command: str) -> str:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(self.cfg.timeout)
        try:
            self._sock.connect((self.cfg.host, self.cfg.port))

            # 1. Kimlik Doğrulama (Authentication)
            self._send_packet(1, self.SERVERDATA_AUTH, self.cfg.password)
            req_id, p_type, _ = self._read_packet()
            if req_id == -1:
                raise PermissionError("RCON sifresi hatali.")

            # 2. Komut Gönderme (Execute Command)
            self._send_packet(2, self.SERVERDATA_EXECCOMMAND, command)
            _, _, response = self._read_packet()
            return response
        finally:
            if self._sock:
                self._sock.close()


