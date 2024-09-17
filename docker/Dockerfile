FROM python:3.11-slim AS build

ARG INSTALL_TYPE=pypi

ENV PIP_DEFAULT_TIMEOUT=100 \
    # Allow statements and log messages to immediately appear
    PYTHONUNBUFFERED=1 \
    # disable a pip version check to reduce run-time & log-spam
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # cache is useless in docker image, so disable to reduce image size
    PIP_NO_CACHE_DIR=1


RUN set -ex \
    # Create a non-root user
    && addgroup --system --gid 1001 appgroup \
    && useradd --uid 1001 --gid 1001 -s /usr/bin/bash -m -d /app appuser \
    && usermod -aG sudo appuser \
    # Upgrade the package index and install security upgrades
    && apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y git build-essential curl libffi-dev \
    python3-dev libssl-dev libxml2-dev libxslt-dev telnet \
    # Install dependencies
    # Clean up
    && apt-get autoremove -y \
    && apt-get clean -y


### Final stage
FROM build AS final
WORKDIR /app

RUN pip3 install git+https://github.com/hemna/aprsd-exporter.git

ADD run.sh /app/run.sh

EXPOSE 8080

ENTRYPOINT ["/app/run.sh"]
