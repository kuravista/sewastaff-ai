from arq.connections import RedisSettings
from arq import cron

from app.workers.message_handler import handle_message
from app.workers.session_watchdog import check_sessions
from app.core.config import settings


class WorkerSettings:
    functions = [handle_message]
    cron_jobs = [cron(check_sessions, minute={0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58})]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 60
    max_tries = 3
    on_startup = None
    on_shutdown = None
