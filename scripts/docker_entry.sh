#!/usr/bin/env bash
set -euo pipefail

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# Adjust appuser GID if needed
if [[ "${PGID}" != "1000" ]]; then
    if getent group "${PGID}" > /dev/null 2>&1; then
        printf "WARNING: GID %s is already in use, skipping groupmod\n" "${PGID}" >&2
    else
        groupmod -o -g "${PGID}" appuser
    fi
fi

# Adjust appuser UID if needed
if [[ "${PUID}" != "1000" ]]; then
    if getent passwd "${PUID}" > /dev/null 2>&1; then
        printf "WARNING: UID %s is already in use, skipping usermod\n" "${PUID}" >&2
    else
        usermod -o -u "${PUID}" appuser
    fi
fi

# Set ownership of app directory (non-recursive to avoid touching bind mounts)
chown "${PUID}:${PGID}" /app

# Optional: restore the database from the most recent S3 backup.
# This drops and recreates the database before anything else runs, so any
# subsequent migrate / seed steps operate on the restored database. Typically
# set VAPI_DOCKER_MIGRATE=true alongside this so the schema is brought up to
# date with the current code.
if [[ "${VAPI_DOCKER_RESTORE:-}" == "true" ]]; then
    printf "VAPI_DOCKER_RESTORE is set to true - restoring database from most recent S3 backup\n"
    gosu appuser app restore --yes
fi

# Optional: run database migrations
if [[ "${VAPI_DOCKER_MIGRATE:-}" == "true" ]]; then
    printf "VAPI_DOCKER_MIGRATE is set to true - running migrations\n"
    gosu appuser app migrate
fi

# Optional: seed reference data
if [[ "${VAPI_DOCKER_SEED:-}" == "true" ]]; then
    printf "VAPI_DOCKER_SEED is set to true - seeding reference data\n"
    gosu appuser app seed
fi

# Optional: create developer user
if [[ "${VAPI_APIUSER_USERNAME:-}" && "${VAPI_APIUSER_EMAIL:-}" ]]; then
    printf "Creating Developer\n"
    arguments=("--username" "${VAPI_APIUSER_USERNAME}" "--email" "${VAPI_APIUSER_EMAIL}")
    if [[ "${VAPI_APIUSER_IS_GLOBAL_ADMIN:-}" == "true" ]]; then
        arguments+=("--global-admin")
    fi
    gosu appuser app developer create "${arguments[@]}"
fi

# Drop privileges and start the server
exec gosu appuser app run
