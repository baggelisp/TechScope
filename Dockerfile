# syntax=docker/dockerfile:1

# Builder: resolve the locked dependencies and install the package into a self-contained venv.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so editing source does not invalidate the dependency layer.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable


# The web framework rides in its own stage, so the graded CLI image never carries it.
FROM builder AS api-builder

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --extra api


# Runtime: no uv, no build tools, no source tree — only the venv, run as a non-root user.
FROM python:3.13-slim-bookworm AS runtime

RUN useradd --create-home --uid 1000 techscope

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER techscope


FROM runtime AS cli

COPY --from=builder --chown=techscope:techscope /app/.venv /app/.venv

# Callers bind-mount the directory holding the domains file here.
WORKDIR /data

ENTRYPOINT ["techscope"]
CMD ["--help"]


FROM runtime AS api

COPY --from=api-builder --chown=techscope:techscope /app/.venv /app/.venv

WORKDIR /app
EXPOSE 8000

# `--factory` because the application is built by a call, which is what lets a test inject a
# service in place of the one the lifespan would wire.
ENTRYPOINT ["uvicorn", "techscope.presentation.api.app:create_app", "--factory"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
