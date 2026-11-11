import syslog

# Doğrudan /dev/log Unix Domain Socket'ine ayrı etiketle yazar
class SystemdAuditLogger:
    def __init__(self, tag: str = "api-audit"):
        self.tag = tag

    def log(self, key_name: str, method: str, path: str, ip: str, status: str = "200 OK"):
        # Format: [Kullanıcı] METHOD /path -> STATUS (IP)
        syslog.openlog(ident=self.tag, facility=syslog.LOG_LOCAL0)
        syslog.syslog(syslog.LOG_INFO, self._format_msg(key_name, method, path, ip, status))
        syslog.closelog()

    def _format_msg(self, key_name:str, method:str, path:str, ip:str, status:str) -> str:
        return f"[{method.ljust(4)}] [IP {ip.ljust(15)}] U={f"'{key_name}'".ljust(16)} ':{path}' | {status}"

audit_logger = SystemdAuditLogger(tag="api-audit")
