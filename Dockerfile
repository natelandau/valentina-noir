FROM ghcr.io/astral-sh/uv:0.9.25-python3.14-bookworm-slim

# Set labels
LABEL org.opencontainers.image.source=https://github.com/natelandau/valentina-noir
LABEL org.opencontainers.image.description="Valentina Noir"
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.url=https://github.com/natelandau/valentina-noir
LABEL org.opencontainers.image.title="Valentina Noir"

# Install Apt Packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates tar git tini tzdata cron \
    build-essential libc6-dev

# Set timezone
ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ >/etc/timezone

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Set the working directory
WORKDIR /app

# Copy the project into the image
COPY uv.lock pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY scripts/ ./scripts/

# Copy files used by valentina
# COPY user_guide.md CHANGELOG.md ./

RUN uv sync --locked --no-dev --no-cache

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Use tini as the entrypoint
ENTRYPOINT ["tini", "--"]

# Run valentina by default
CMD ["scripts/docker_entry.sh"]
