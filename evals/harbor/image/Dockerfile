# syntax=docker/dockerfile:1.7

ARG RUST_IMAGE=rust:1.85.1-slim-bookworm@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36
ARG PYTHON_IMAGE=python:3.10.21-slim-bookworm@sha256:673f009e3763f8d03953b525c89b03a9ee8ca315bf6b8006979b5c4a4e2e4d68

FROM ${RUST_IMAGE} AS rust-toolchain
FROM ${PYTHON_IMAGE}

ARG UV_VERSION=0.11.26
ARG PYTHON_311=3.11.15
ARG PYTHON_312=3.12.13
ARG PYTHON_313=3.13.14
ARG PYTHON_314=3.14.6

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_HOME=/usr/local/cargo \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_FIND_LINKS=/opt/typewriter/wheelhouse \
    PRE_COMMIT_HOME=/opt/typewriter/pre-commit \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RUSTUP_HOME=/usr/local/rustup \
    UV_OFFLINE=1 \
    UV_PYTHON_INSTALL_DIR=/opt/typewriter/python \
    UV_PYTHON_PREFERENCE=only-managed \
    PATH=/workspace/typewriter/.venv/bin:/opt/typewriter/venvs/py310/bin:/usr/local/cargo/bin:/usr/local/bin:/usr/bin:/bin

COPY --from=rust-toolchain /usr/local/cargo /usr/local/cargo
COPY --from=rust-toolchain /usr/local/rustup /usr/local/rustup

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        git \
        jq \
        patch \
        passwd \
        rsync \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir "uv==${UV_VERSION}"

ENV PIP_NO_INDEX=1

COPY evals/harbor/image/requirements.lock /opt/typewriter/requirements.lock

RUN UV_OFFLINE=0 uv python install "${PYTHON_311}" "${PYTHON_312}" "${PYTHON_313}" "${PYTHON_314}" \
    && uv venv --python /usr/local/bin/python /opt/typewriter/venvs/py310 \
    && uv venv --python "${PYTHON_311}" /opt/typewriter/venvs/py311 \
    && uv venv --python "${PYTHON_312}" /opt/typewriter/venvs/py312 \
    && uv venv --python "${PYTHON_313}" /opt/typewriter/venvs/py313 \
    && uv venv --python "${PYTHON_314}" /opt/typewriter/venvs/py314 \
    && for version in 310 311 312 313 314; do \
        PIP_NO_INDEX=0 UV_OFFLINE=0 uv pip install \
            --python "/opt/typewriter/venvs/py${version}/bin/python" \
            --require-hashes \
            --requirement /opt/typewriter/requirements.lock; \
    done \
    && mkdir -p /opt/typewriter/wheelhouse \
    && /opt/typewriter/venvs/py310/bin/python -m ensurepip --upgrade \
    && PIP_NO_INDEX=0 /opt/typewriter/venvs/py310/bin/python -m pip download \
        --dest /opt/typewriter/wheelhouse \
        --require-hashes \
        --requirement /opt/typewriter/requirements.lock

COPY .pre-commit-config.yaml /tmp/typewriter-pre-commit/.pre-commit-config.yaml

RUN git init -q /tmp/typewriter-pre-commit \
    && cd /tmp/typewriter-pre-commit \
    && PIP_NO_INDEX=0 UV_OFFLINE=0 /opt/typewriter/venvs/py310/bin/pre-commit install-hooks \
    && rm -rf /tmp/typewriter-pre-commit \
    && chmod -R a+rwX /opt/typewriter/pre-commit

RUN /usr/sbin/useradd --create-home --uid 1000 --shell /bin/bash agent \
    && mkdir -p /workspace/typewriter /logs/agent /logs/verifier /logs/artifacts \
    && chown -R agent:agent /workspace /logs /opt/typewriter/pre-commit \
    && chmod -R a+rX /opt/typewriter/wheelhouse

COPY --chmod=755 evals/harbor/image/smoke-test.sh /usr/local/bin/typewriter-image-smoke-test
RUN typewriter-image-smoke-test

WORKDIR /workspace/typewriter
