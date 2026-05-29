from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, merge_contextvars


SERVICE_NAME = "sewastaff-ai"


def add_service(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    event_dict["service"] = SERVICE_NAME
    return event_dict


def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    structlog.configure(
        processors=[
            merge_contextvars,
            add_service,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    return structlog.get_logger(name)


def bind_correlation_id(cid: str) -> None:
    bind_contextvars(correlation_id=str(cid))
