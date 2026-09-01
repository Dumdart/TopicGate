#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"
compose_file="$script_dir/docker-compose.yml"
env_file="$script_dir/.env"
state_file="$script_dir/.run-state.json"
project_name="topicgate-zigbee2mqtt-demo"
profile_name="Zigbee2MQTT Demo"
topic_filter="zigbee2mqtt/#"
publisher_pid=""
profile_created="false"
subscription_created="false"

set -a
# shellcheck disable=SC1091
source <(sed 's/\r$//' "$env_file")
set +a

compose() {
    docker compose \
        --project-name "$project_name" \
        -f "$compose_file" \
        --env-file "$env_file" \
        "$@"
}

state_value() {
    uv run python -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]])' \
        "$state_file" "$1"
}

write_state() {
    uv run python -c \
        'import json,sys; from pathlib import Path; Path(sys.argv[1]).write_text(json.dumps({"profile_created": sys.argv[2] == "true", "subscription_created": sys.argv[3] == "true", "data_dir": sys.argv[4]}, indent=2) + "\n", encoding="utf-8")' \
        "$state_file" "$profile_created" "$subscription_created" \
        "${TOPICGATE_DATA_DIR:-}"
}

stop_publisher() {
    if [[ -n "$publisher_pid" ]] && kill -0 "$publisher_pid" 2>/dev/null; then
        kill -TERM "$publisher_pid" 2>/dev/null || true
        wait "$publisher_pid" 2>/dev/null || true
    fi
    publisher_pid=""
}

runtime_cleanup() {
    stop_publisher
    compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    if [[ -f "$state_file" ]]; then
        printf '\nDemo configuration is still recorded. Close TopicGate, then run:\n'
        printf '  bash demo/zigbee2mqtt_scenario/run_demo.sh cleanup\n'
    fi
}

cleanup_owned_configuration() {
    if [[ ! -f "$state_file" ]]; then
        return
    fi

    local recorded_data_dir
    recorded_data_dir="$(state_value data_dir)"
    if [[ -n "$recorded_data_dir" ]]; then
        export TOPICGATE_DATA_DIR="$recorded_data_dir"
    else
        unset TOPICGATE_DATA_DIR || true
    fi

    if [[ "$(state_value profile_created)" == "True" ]]; then
        uv run topicgate-cli profile remove --name "$profile_name"
    elif [[ "$(state_value subscription_created)" == "True" ]]; then
        uv run topicgate-cli sub remove --name "$profile_name" --topic "$topic_filter"
    fi
    rm -f -- "$state_file"
}

configure_topicgate() {
    local profile_line
    profile_line="$(
        uv run topicgate-cli profile list |
            awk -F '\t' -v name="$profile_name" '$2 == name { print; exit }'
    )"

    if [[ -z "$profile_line" ]]; then
        printf '%s\n' "$MQTT_PASSWORD" |
            uv run topicgate-cli profile add \
                --name "$profile_name" \
                --host localhost \
                --port "$MQTT_PORT" \
                --username "$MQTT_USERNAME" \
                --password-stdin
        profile_created="true"
        write_state
    else
        local profile_id existing_name existing_host existing_port
        local existing_username existing_tls
        IFS=$'\t' read -r profile_id existing_name existing_host existing_port \
            existing_username existing_tls <<< "$profile_line"
        if [[ "$existing_host" != "localhost" || \
              "$existing_port" != "$MQTT_PORT" || \
              "$existing_username" != "$MQTT_USERNAME" || \
              "$existing_tls" != "False" ]]; then
            printf 'Existing profile "%s" does not match the demo broker.\n' \
                "$profile_name" >&2
            return 1
        fi
    fi

    uv run topicgate-cli profile test --name "$profile_name"

    local subscription_line
    subscription_line="$(
        uv run topicgate-cli sub list --name "$profile_name" |
            awk -F '\t' -v topic="$topic_filter" '$1 == topic { print; exit }'
    )"
    if [[ -z "$subscription_line" ]]; then
        uv run topicgate-cli sub add \
            --name "$profile_name" \
            --topic "$topic_filter" \
            --retain-as-published
        subscription_created="true"
        write_state
    elif [[ "$subscription_line" != $'zigbee2mqtt/#\t1\tTrue\t0' ]]; then
        printf 'Existing "%s" subscription has incompatible options.\n' \
            "$topic_filter" >&2
        return 1
    fi
}

start_publisher() {
    local phase="$1"
    uv run python demo/zigbee2mqtt_scenario/publisher.py \
        --host localhost --port "$MQTT_PORT" --phase "$phase" &
    publisher_pid="$!"
}

pause() {
    printf '\n%s\n' "$1"
    read -r -p "Press Enter to continue... "
}

trap runtime_cleanup EXIT
cd "$repo_root"

if [[ "${1:-}" == "cleanup" ]]; then
    compose down --volumes --remove-orphans
    cleanup_owned_configuration
    printf 'Demo broker, volumes, and demo-owned TopicGate configuration removed.\n'
    exit 0
fi
if [[ $# -ne 0 ]]; then
    printf 'Usage: %s [cleanup]\n' "$0" >&2
    exit 2
fi
if [[ -f "$state_file" ]]; then
    printf 'A previous run needs cleanup. Close TopicGate, then run:\n' >&2
    printf '  bash demo/zigbee2mqtt_scenario/run_demo.sh cleanup\n' >&2
    exit 1
fi

write_state
printf 'Starting the disposable Mosquitto broker...\n'
compose up -d --wait
configure_topicgate

pause "Start TopicGate Desktop, select '$profile_name', connect, and keep it open."
start_publisher full
pause "Wait for 'Scenario full phase ready', then inspect the five demo conditions."

stop_publisher
pause "Close TopicGate Desktop completely. This preserves the attic observation for the stale demonstration."
pause "Restart TopicGate Desktop, select '$profile_name', connect, and keep it open."

start_publisher healthy
pause "The kitchen sensor is now Live while the cached attic sensor is Stale. Inspect the result, then close TopicGate Desktop."

stop_publisher
cleanup_owned_configuration
printf '\nDemo complete. Disposable broker and demo-owned configuration will be removed.\n'
