#!/usr/bin/env bash
set -x

# The default command
# Override the command in docker-compose.yml to change
# what command you want to run in the container

APRSD_URL=${APRSD_URL:-http://localhost:8080}
UPDATE_INTERVAL=${UPDATE_INTERVAL:-60}

aprsd_exporter --aprsd-url ${APRSD_URL} --update-interval ${UPDATE_INTERVAL}