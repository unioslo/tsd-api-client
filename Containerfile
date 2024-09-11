ARG PYTHON_VERSION="3.12"
ARG BASE_IMAGE="docker.io/python:${PYTHON_VERSION}-alpine"

FROM ${BASE_IMAGE} AS poetry

RUN apk add --no-cache \
    build-base \
    libffi-dev
ARG POETRY_VERSION="1.8.3"
RUN pip install poetry==${POETRY_VERSION}


FROM poetry AS builder
WORKDIR /src
COPY poetry.lock pyproject.toml README.md LICENSE ./

RUN python -m venv /app && \
    source /app/bin/activate && \
    poetry install --only main --no-root

ARG POETRY_DYNAMIC_VERSIONING_VERSION="1.4.1"
RUN poetry self add "poetry-dynamic-versioning[plugin]==${POETRY_DYNAMIC_VERSIONING_VERSION}"
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
VOLUME [ "/config/tacl" ]
COPY --from=builder /app /app
