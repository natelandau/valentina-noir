# ============================================================
# Stage 1: Builder - install dependencies and compile
# ============================================================
FROM ghcr.io/astral-sh/uv:0.11.3-python3.13-trixie-slim AS builder

# Build-time system deps for native extensions (numpy, argon2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libc6-dev \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1

WORKDIR /app

# Install dependencies first (cached unless lock/pyproject changes)
COPY uv.lock pyproject.toml README.md LICENSE ./
RUN uv sync --locked --no-dev --no-cache --no-install-project

# Install the project itself
COPY src/ ./src/
RUN uv sync --locked --no-dev --no-cache

# ============================================================
# Stage 2: Runtime - lean production image
# ============================================================
FROM python:3.13-slim-trixie

# Runtime-only system deps
# Install PGDG apt repo to get postgresql-client-18 (Debian trixie ships v17,
# which is incompatible with a Postgres 18 server used by the backup task)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates tini tzdata gosu libargon2-1 gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

# Timezone
ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ >/etc/timezone

# Create default app user
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# PUID/PGID defaults (overridden at runtime via env vars)
ENV PUID=1000
ENV PGID=1000

WORKDIR /app

# Copy the built venv from builder
COPY --from=builder /app/.venv .venv

# Copy source and scripts
COPY src/ ./src/
COPY scripts/ ./scripts/
RUN chmod +x scripts/docker_entry.sh

ENV PATH="/app/.venv/bin:$PATH"

# OCI labels (placed after stable layers to avoid cache busting)
LABEL org.opencontainers.image.source=https://github.com/natelandau/valentina-noir
LABEL org.opencontainers.image.description="Valentina Noir"
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/natelandau/valentina-noir
LABEL org.opencontainers.image.title="Valentina Noir"

ENTRYPOINT ["tini", "--"]
CMD ["scripts/docker_entry.sh"]
