"""Configuration for the SAQ Plugin."""

from litestar_saq import CronJob, QueueConfig, SAQConfig

from vapi.config import settings

saq_settings = SAQConfig(
    web_enabled=settings.saq.web_enabled,
    worker_processes=settings.saq.processes,
    use_server_lifespan=settings.saq.use_server_lifespan,
    queue_configs=[
        QueueConfig(
            dsn=settings.redis.url,
            name="purge-db-expired-items",
            tasks=["vapi.lib.scheduled_tasks.purge_db_expired_items"],
            scheduled_tasks=[
                CronJob(
                    function="vapi.lib.scheduled_tasks.purge_db_expired_items",
                    unique=True,
                    cron="0 4 * * *",
                    timeout=300,
                ),
            ],
        ),
    ],
)
