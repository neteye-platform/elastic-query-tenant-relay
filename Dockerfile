# From example at: https://github.com/astral-sh/uv-docker-example/blob/main/multistage.Dockerfile

# Build app dependencies
FROM python:3.14.5-slim-bookworm@sha256:a9bee15510a364124aa24692899d269835683b883de42f7ebec8c293cf679ccb AS builder
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    # Needed by hatch-vcs
    git=1:2.39.5-0+deb12u3 \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11.13@sha256:841c8e6fe30a8b07b4478d12d0c608cba6de66102d29d65d1cc423af86051563 /uv /bin/

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
FROM python:3.14.5-slim-bookworm@sha256:a9bee15510a364124aa24692899d269835683b883de42f7ebec8c293cf679ccb
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
