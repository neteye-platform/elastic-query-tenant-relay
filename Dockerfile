# From example at: https://github.com/astral-sh/uv-docker-example/blob/main/multistage.Dockerfile

# Build app dependencies
FROM python:3.14.4-slim-bookworm@sha256:fc74d22ffd0d5ac395a4b7bdda75a4539758862c49ebf3005647084631e63789 AS builder
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    # Needed by hatch-vcs
    git=1:2.39.5-0+deb12u3 \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11.8@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 /uv /bin/

# Install only dependencies to leverage caching
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    SETUPTOOLS_SCM_PRETEND_VERSION_FOR_EQTR=0 \
    uv sync --locked --no-dev --no-install-project --no-editable

# Build app
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=.git,target=.git \
    uv sync --locked --no-dev --no-editable --reinstall-package=eqtr

# Copy app to runtime stage
FROM python:3.14.4-slim-bookworm@sha256:fc74d22ffd0d5ac395a4b7bdda75a4539758862c49ebf3005647084631e63789
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    dumb-init=1.2.5-2 \
    curl=7.88.1-10+deb12u14 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the app
RUN useradd -m appuser
USER appuser

COPY --from=builder /app/.venv /app/.venv

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

HEALTHCHECK CMD ["curl", "-f", "http://localhost:8000/health"]

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/sh", "-c", "eqtr"]
