FROM ubuntu:24.04

ARG UID=501
ARG GID=20

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      git openssh-client ca-certificates curl \
      build-essential cmake ninja-build ccache python3 python3-pip \
      vim less sudo \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /etc/ssh && ssh-keyscan github.com >> /etc/ssh/ssh_known_hosts 2>/dev/null

RUN userdel -r ubuntu 2>/dev/null || true; \
    if ! getent group "${GID}" >/dev/null; then groupadd -g "${GID}" dev; fi; \
    useradd -m -u "${UID}" -g "${GID}" -s /bin/bash dev; \
    echo 'dev ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/dev

USER dev
WORKDIR /workspace

RUN git config --global --add safe.directory '*'

CMD ["bash"]
