FROM python:3.12-slim-bullseye

ENV PYTHONPATH=/

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /
RUN pip install poetry && poetry install

COPY ./app /app