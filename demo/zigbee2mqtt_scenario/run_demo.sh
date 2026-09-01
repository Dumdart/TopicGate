#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"

set -a
# shellcheck disable=SC1091
source <(sed 's/\r$//' "$script_dir/.env")
set +a

cleanup() {
    docker compose \
        -f "$script_dir/docker-compose.yml" \
        --env-file "$script_dir/.env" \
        down
}

trap cleanup EXIT

docker compose \
    -f "$script_dir/docker-compose.yml" \
    --env-file "$script_dir/.env" \
    up -d --wait

cd "$repo_root"

uv run python demo/zigbee2mqtt_scenario/publisher.py
