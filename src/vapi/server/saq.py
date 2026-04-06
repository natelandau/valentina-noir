"""Configuration for the SAQ Plugin."""

from litestar_saq import CronJob, QueueConfig, SAQConfig

from vapi.config import settings

_scheduled_tasks: list[CronJob] = [
    CronJob(
        function="vapi.lib.scheduled_tasks.purge_db_expired_items",
        unique=True,
        cron="0 4 * * *",
        timeout=300,
    ),
]

_task_paths = ["vapi.lib.scheduled_tasks.purge_db_expired_items"]

if settings.backup.enabled:
    _scheduled_tasks.append(
        CronJob(
            function="vapi.lib.scheduled_tasks.backup_database",
            unique=True,
            cron=settings.backup.cron,
            timeout=600,
        ),
    )
    _task_paths.append("vapi.lib.scheduled_tasks.backup_database")

saq_settings = SAQConfig(
    web_enabled=settings.saq.web_enabled,
    worker_processes=settings.saq.processes,
    use_server_lifespan=settings.saq.use_server_lifespan,
    queue_configs=[
        QueueConfig(
            dsn=settings.redis.url,
            name="scheduled-tasks",
            tasks=_task_paths,
            scheduled_tasks=_scheduled_tasks,
        ),
    ],
)
