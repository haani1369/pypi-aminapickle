#!/usr/bin/env bash
#
# ./docker.sh stop
# ./docker.sh rebuild

set -euo pipefail

IMAGE_NAME="pypi-aminapickle"
CONTAINER_NAME="pypi-aminapickle"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

HOST_SSH_SOCK="/run/host-services/ssh-auth.sock"

GIT_NAME="$(git config --global user.name  2>/dev/null || true)"
GIT_EMAIL="$(git config --global user.email 2>/dev/null || true)"

cmd="${1:-shell}"

case "$cmd" in
  stop)
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    echo ">> Stopped $CONTAINER_NAME (state preserved; run ./docker.sh to resume)."
    exit 0
    ;;
  rebuild)
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker image rm -f "$IMAGE_NAME" >/dev/null 2>&1 || true
    echo ">> Removed container and image. Re-run ./docker.sh to build fresh."
    exit 0
    ;;
  shell) ;;  # fall through to the main flow
  *)
    echo "usage: ./docker.sh [stop|rebuild]" >&2
    exit 1
    ;;
esac

if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo ">> Building image $IMAGE_NAME ..."
  docker build \
    --build-arg UID="$(id -u)" \
    --build-arg GID="$(id -g)" \
    -t "$IMAGE_NAME" \
    "$REPO_DIR"
fi

if ! docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  echo ">> Creating container $CONTAINER_NAME ..."
  docker run -d --init \
    --name "$CONTAINER_NAME" \
    -v "$REPO_DIR":/workspace \
    -v "$HOST_SSH_SOCK":/ssh-agent \
    -e SSH_AUTH_SOCK=/ssh-agent \
    -e GIT_AUTHOR_NAME="$GIT_NAME" \
    -e GIT_AUTHOR_EMAIL="$GIT_EMAIL" \
    -e GIT_COMMITTER_NAME="$GIT_NAME" \
    -e GIT_COMMITTER_EMAIL="$GIT_EMAIL" \
    "$IMAGE_NAME" \
    sleep infinity >/dev/null
fi

if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null)" != "true" ]; then
  echo ">> Starting container $CONTAINER_NAME ..."
  docker start "$CONTAINER_NAME" >/dev/null
fi

exec docker exec -it "$CONTAINER_NAME" bash
