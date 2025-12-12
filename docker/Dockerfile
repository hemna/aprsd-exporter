FROM ghcr.io/astral-sh/uv:python3.11-alpine AS build

ARG INSTALL_TYPE=pypi

ENV PYTHONUNBUFFERED=1

# Create a non-root user and install dependencies
RUN set -ex \
    && addgroup -S -g 1001 appgroup \
    && adduser -S -u 1001 -G appgroup -s /bin/sh -D -h /app appuser \
    && apk update \
    && apk upgrade \
    && apk add --no-cache git curl gcc musl-dev libffi-dev \
        openssl-dev libxml2-dev libxslt-dev bash


### Final stage
FROM build AS final
WORKDIR /app

RUN uv venv
RUN uv pip install git+https://github.com/hemna/aprsd-exporter.git

ADD run.sh /app/run.sh

EXPOSE 8080

ENTRYPOINT ["/app/run.sh"]
