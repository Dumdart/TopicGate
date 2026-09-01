
import argparse
from collections.abc import Sequence
from getpass import getpass
import sys

from topicgate.app.app_dependencies import AppDependencies
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.infrastructure import mqtt

def add_profile(args: argparse.Namespace) -> int:
    dependencies = AppDependencies()

    # Securely prompt for password
    password = getpass("MQTT password: ")

    config = MqttConfig(
        username=args.username,
        host=args.host,
        port=args.port,
        password=password,
        use_tls=args.use_tls,
    )

    try:
        dependencies.broker_profiles.create_profile(args.name, config)
        dependencies.broker_profiles.save()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="topicgate-cli")
    commands = parser.add_subparsers(dest="command", required=True)

    profile_parser = commands.add_parser("profile", help="Manage broker profiles")
    profile_commands = profile_parser.add_subparsers(dest="profile_command", required=True)

    add_profile_parser = profile_commands.add_parser("add", help="Add a new profile")
    add_profile_parser.add_argument("--name", help="Profile name", required=True)
    add_profile_parser.add_argument("--host", default="localhost", help="MQTT broker host")
    add_profile_parser.add_argument("--port", default=1883, help="MQTT broker port")
    add_profile_parser.add_argument("--username", default="", help="MQTT username")
    add_profile_parser.add_argument("--use-tls", default=False, help="Use TLS")
    add_profile_parser.set_defaults(handler=add_profile)

    return parser

def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)
