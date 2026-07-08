import logging
from collections import deque
from datetime import datetime


class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=500):
        super().__init__()
        self.buffer = deque(maxlen=capacity)
        self.setFormatter(logging.Formatter(
            "%(asctime)s.%(msecs)03dZ",
            datefmt="%Y-%m-%dT%H:%M:%S"
        ))

    def emit(self, record):
        try:
            self.buffer.append({
                "timestamp": self.format(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "line": record.lineno,
            })
        except Exception:
            self.handleError(record)

    def get_logs(self, level=None, limit=50, offset=0):
        logs = list(self.buffer)
        logs.reverse()
        if level:
            level_upper = level.upper()
            logs = [l for l in logs if l["level"] == level_upper]
        total = len(logs)
        page = logs[offset:offset + limit]
        return {"total": total, "logs": page}
