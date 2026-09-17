# From example at: https://github.com/astral-sh/uv-docker-example/blob/main/multistage.Dockerfile

# Build app dependencies
FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS builder
WORKDIR /app

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    # Needed by hatch-vcs
    git \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.12.15@sha256:62f8c047d0a0e9ece6b53fc63df902585a67a47a7f318ddec4a37db586edc8e3 /uv /bin/

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
FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f
WORKDIR /app

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    curl \
    dumb-init \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the app
RUN groupadd --gid 10001 appuser \
    && useradd --create-home --uid 10001 --gid 10001 appuser
USER 10001:10001

COPY --from=builder /app/.venv /app/.venv

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["curl", "--fail", "--silent", "--show-error", "http://127.0.0.1:8000/health"]

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["eqtr"]
