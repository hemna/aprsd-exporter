FROM ghcr.io/astral-sh/uv:python3.11-alpine AS build

ARG INSTALL_TYPE=pypi

ENV PYTHONUNBUFFERED=1


RUN set -ex \
    # Create a non-root user
    && addgroup --system --gid 1001 appgroup \
    && adduser --uid 1001 --gid 1001 -s /bin/sh -D -h /app appuser \
    # Upgrade the package index and install dependencies
    && apk update \
    && apk upgrade \
    && apk add --no-cache git curl gcc musl-dev libffi-dev \
    openssl-dev libxml2-dev libxslt-dev bash


### Final stage
FROM build AS final
WORKDIR /app

RUN uv pip install git+https://github.com/hemna/aprsd-exporter.git

ADD run.sh /app/run.sh

EXPOSE 8080

ENTRYPOINT ["/app/run.sh"]
