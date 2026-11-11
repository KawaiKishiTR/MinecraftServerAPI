import syslog

# Doğrudan /dev/log Unix Domain Socket'ine ayrı etiketle yazar
class SystemdAuditLogger:
    def __init__(self, tag: str = "api-audit"):
        self.tag = tag

    def log(self, key_name: str, method: str, path: str, ip: str, status: str = "200 OK"):
        # Format: [Kullanıcı] METHOD /path -> STATUS (IP)
        msg = f"user='{key_name}' client_ip='{ip}' method='{method}' path='{path}' status={status}"
        syslog.openlog(ident=self.tag, facility=syslog.LOG_LOCAL0)
        syslog.syslog(syslog.LOG_INFO, msg)
        syslog.closelog()

audit_logger = SystemdAuditLogger(tag="api-audit")