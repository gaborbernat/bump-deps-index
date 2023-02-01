FROM ubuntu:22.10

RUN apt-get update && \
    apt-get install --yes --no-install-recommends git \
        python3-dev python3-pip python3-venv && \
    rm -rf /opt/bb/var/cache/apt

RUN python3.10 -m pip install tox
