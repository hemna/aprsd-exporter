#!/usr/bin/env bash
set -x

# Default values
APRSD_URL=${APRSD_URL:-http://localhost:8080}
UPDATE_INTERVAL=${UPDATE_INTERVAL:-60}
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8080}
API_PORT=${API_PORT:-8081}

source /app/.venv/bin/activate

# Build the command
CMD="aprsd_exporter --host ${HOST} --port ${PORT} --update-interval ${UPDATE_INTERVAL}"

if [ -n "${STATS_FILE}" ]; then
    CMD="${CMD} --stats-file ${STATS_FILE}"
elif [ -n "${API}" ] && [ "${API}" = "true" ]; then
    CMD="${CMD} --api --api-port ${API_PORT}"
else
    CMD="${CMD} --aprsd-url ${APRSD_URL}"
fi

# Add optional flags
if [ -n "${DEBUG}" ] && [ "${DEBUG}" = "true" ]; then
    CMD="${CMD} --debug"
fi

if [ -n "${QUIET}" ] && [ "${QUIET}" = "true" ]; then
    CMD="${CMD} --quiet"
fi

# Execute the command
exec ${CMD}
