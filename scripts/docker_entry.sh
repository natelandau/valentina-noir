#! /usr/bin/env bash

if not command -v uv &> /dev/null; then
    echo "uv is not installed"
    exit 1
fi

# Check if VAPI_BOOTSTRAP environment variable is set to true
if [[ "${VAPI_DOCKER_BOOTSTRAP}" == "true" ]]; then
    echo "VAPI_DOCKER_BOOTSTRAP is set to true - running bootstrap"
    uv run --no-dev app bootstrap
fi

if [[ "${VAPI_APIUSER_USERNAME}" && "${VAPI_APIUSER_EMAIL}" ]]; then
    echo "Creating Developer"
    arguments=("--username" "${VAPI_APIUSER_USERNAME}" "--email" "${VAPI_APIUSER_EMAIL}")
    if [[ "${VAPI_APIUSER_IS_GLOBAL_ADMIN}" == "true" ]]; then
        arguments+=("--global-admin")
    fi
    uv run --no-dev app developer create "${arguments[@]}"
fi

# Run the server
uv run --no-dev app run
