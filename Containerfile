ARG BASE_IMAGE="docker.io/python:3.12-alpine"

FROM ${BASE_IMAGE} AS poetry

RUN apk add --no-cache \
    build-base \
    libffi-dev
RUN pip install poetry==1.3.2


FROM poetry AS builder
WORKDIR /src
COPY poetry.lock pyproject.toml README.md LICENSE ./

RUN python -m venv /app && \
    source /app/bin/activate && \
    poetry install --only main --no-root

RUN poetry self add "poetry-dynamic-versioning[plugin]==1.1.0"
RUN apk add --no-cache git
COPY tsdapiclient ./tsdapiclient
COPY .git ./.git
RUN source /app/bin/activate && \
    poetry build --format wheel --no-interaction && \
    pip install dist/*.whl


FROM ${BASE_IMAGE} AS runtime
LABEL org.opencontainers.image.title="TSD API Client" \
      org.opencontainers.image.description="Command line client for the TSD HTTP API" \
      org.opencontainers.image.url="https://github.com/unioslo/tsd-api-client" \
      org.opencontainers.image.source="https://github.com/unioslo/tsd-api-client"
ENTRYPOINT [ "/app/bin/tacl" ]
ENV XDG_CONFIG_HOME=/config
VOLUME [ "/config" ]
COPY --from=builder /app /app
