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


# Runtime: no uv, no build tools, no source tree — only the venv, run as a non-root user.
FROM python:3.13-slim-bookworm AS cli

RUN useradd --create-home --uid 1000 techscope

COPY --from=builder --chown=techscope:techscope /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER techscope
# Callers bind-mount the directory holding the domains file here.
WORKDIR /data

ENTRYPOINT ["techscope"]
CMD ["--help"]
