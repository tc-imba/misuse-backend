# syntax=docker/dockerfile:1
FROM tiangolo/uvicorn-gunicorn:python3.11-slim

ENV HOME="/root"
WORKDIR /root/

# install poetry
ARG PYPI_MIRROR
RUN if [ -n "$PYPI_MIRROR" ]; then pip config set global.index-url $PYPI_MIRROR; fi
RUN --mount=type=cache,target=/root/.cache pip install poetry

# create virtualenv
ENV VIRTUAL_ENV=/root/.venv
RUN python3 -m virtualenv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# install dependencies
COPY ./pyproject.toml ./poetry.lock ./README.md /root/
COPY ./misuse_backend/__init__.py ./poetry.lock ./README.md /root/misuse_backend/
RUN --mount=type=cache,target=/root/.cache poetry install --no-dev
COPY ./misuse_backend /root/misuse_backend/
RUN --mount=type=cache,target=/root/.cache poetry install --no-dev

EXPOSE $PORT

CMD python3 -m misuse_backend
