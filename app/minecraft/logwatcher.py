from typing import Callable, Optional
from collections import deque
import subprocess
import threading
import logging

from app.config import MCLogsConfig


class SystemctlLogWatcher:
    WAIT_SECONDS_BEFORE_STOP:int = 60
    def __init__(self, cfg: MCLogsConfig):
        self.cfg = cfg
        self.buffer: deque[str] = deque(maxlen=cfg.line_count) 

        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False

        self.on_line:set[Callable[[str], None]] = set()
        self._lock = threading.Lock()
        self._stop_timer: Optional[threading.Timer] = None

    def start(self) -> None:
        """Log izleyiciyi arka plan thread'i olarak başlatır."""
        if self._running:
            return

        self._running = True

        # -n 0 parametresi geçmişi atlayıp sadece yeni düşen logları dinler.
        # Geçmişten de log almak istersen -n parametresini kaldırabilirsin.
        lines_arg = str(self.cfg.line_count) if self.cfg.line_count else "50"
        cmd = ["journalctl", "-u", self.cfg.service_name, "-f", "-n", lines_arg]

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # Çıktıyı str (string) olarak çözer
            bufsize=1,  # Line buffering (satır bazlı iletim)
        )

        self._thread = threading.Thread(
            target=self._stream_reader, daemon=True
        )
        self._thread.start()

    def _stream_reader(self) -> None:
        """stdout akışını satır satır deque buffer'ına yazar."""
        if not self._process or not self._process.stdout:
            return

        # iter(..., '') veya doğrudan döngü satır tamamlandıkça (newline) tetiklenir
        for line in self._process.stdout:
            if not self._running:
                break
            clean_line = line.rstrip("\n")
            self.buffer.append(clean_line)

            with self._lock:
                subscribers = list(self.on_line)

            for sub in subscribers:
                try:
                    sub(clean_line)
                except Exception as e:
                    logging.error(f"Callback ERROR: {e}")

    def get_logs(self) -> list[str]:
        """Mevcut buffer içeriğini liste olarak döndürür."""
        return list(self.buffer)

    def subscribe(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            self.on_line.add(callback)

            if self._stop_timer:
                self._stop_timer.cancel()
                self._stop_timer = None

        if not self._running:
            self.start()

    def unsubscribe(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            self.on_line.discard(callback)

            if len(self.on_line) == 0 and self._stop_timer is None:
                self._stop_timer = threading.Timer(
                    self.WAIT_SECONDS_BEFORE_STOP, self._timer_stopped
                )
                self._stop_timer.daemon = True
                self._stop_timer.start()

    def _timer_stopped(self) -> None:
        with self._lock:
            self._stop_timer = None
            if len(self.on_line) == 0:
                self.stop()

    def stop(self) -> None:
        """Alt süreci ve thread'i güvenli şekilde sonlandırır."""
        self._running = False

        with self._lock:
            if self._stop_timer:
                self._stop_timer.cancel()
                self._stop_timer = None

        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()

        if self._thread and self._thread.is_alive():
            # Thread okuma yaparken stdout kapandığı için kendiliğinden düşecektir
            self._thread.join(timeout=1)
