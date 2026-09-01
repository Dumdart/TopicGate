
import argparse
from collections.abc import Sequence
from getpass import getpass
import sys

from topicgate.app.app_dependencies import AppDependencies
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.subscription import Subscription


def _print_error(error: Exception) -> None:
    message = error.args[0] if isinstance(error, KeyError) else str(error)
    print(f"Error: {message}", file=sys.stderr)

def list_profiles(args: argparse.Namespace) -> int:
    dependencies = AppDependencies()

    for profile in dependencies.broker_profiles.list_profile_summaries():
        print(
            profile.id,
            profile.name,
            profile.host,
            profile.port,
            profile.username,
            profile.use_tls,
            sep="\t",
        )

    return 0


def add_profile(args: argparse.Namespace) -> int:
    dependencies = AppDependencies()

    try:
        profile = dependencies.broker_profiles.get_profile_by_name(args.name)
    except KeyError:
        pass
    else:
        print(f"Broker profile already exists: {profile.name}")
        return 0

    # Securely prompt for password
    password = "" if args.no_password else getpass("MQTT password: ")

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

    except (KeyError, ValueError) as error:
        _print_error(error)
        return 1

    return 0

def add_subscription(args: argparse.Namespace) -> int:
    dependencies = AppDependencies()

    try:
        profile = dependencies.broker_profiles.get_profile_by_name(args.name)
        subscription = dependencies.broker_profiles.add_subscription(
            profile.id,
            Subscription(
                topic_filter=args.topic,
                qos=args.qos,
                retain_as_published=args.retain_as_published,
                retain_handling=args.retain_handling,
            ),
        )
    except ValueError as error:
        if "already exists" in str(error):
            print(f"Subscription already exists: {args.topic}")
            return 0
        _print_error(error)
        return 1
    except KeyError as error:
        _print_error(error)
        return 1

    print(f"Subscription added: {subscription}")

    return 0

def test_profile(args: argparse.Namespace) -> int:
    dependencies = AppDependencies()

    try:
        for profile in dependencies.broker_profiles.get_all_profiles():
            print(f"Testing profile: {profile.name}")
            dependencies.broker_profiles.test_profile(profile.id)
    except KeyError as error:
        _print_error(error)
        return 1

    return 0

def remove_subscription(args: argparse.Namespace) -> int:
    dependencies = AppDependencies()

    try:
        profile = dependencies.broker_profiles.get_profile_by_name(args.name)
        subscription = dependencies.broker_profiles.remove_subscription(
            profile.id,
            args.topic,
        )
    except (KeyError, ValueError) as error:
        _print_error(error)
        return 1

    print(f"Subscription removed: {subscription}")

    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="topicgate-cli")
    commands = parser.add_subparsers(dest="command", required=True)

    profile_parser = commands.add_parser("profile", help="Manage broker profiles")
    profile_commands = profile_parser.add_subparsers(dest="profile_command", required=True)

    add_profile_parser = profile_commands.add_parser("add", help="Add a new profile")
    add_profile_parser.add_argument("--name", help='Profile name (e.g. "MyBroker123")', required=True)
    add_profile_parser.add_argument("--host", default="localhost", help="MQTT broker host")
    add_profile_parser.add_argument("--port", default=1883, help="MQTT broker port")
    add_profile_parser.add_argument("--username", default="", help="MQTT username")
    add_profile_parser.add_argument("--use-tls", action="store_true", help="Use TLS")
    add_profile_parser.add_argument("--no-password", action="store_true", help="MQTT password")
    add_profile_parser.set_defaults(handler=add_profile)

    list_profile_parser = profile_commands.add_parser("list", help="List all profiles")
    list_profile_parser.set_defaults(handler=list_profiles)

    test_profile_parser = profile_commands.add_parser("test", help="Test profile connection")
    test_profile_parser.set_defaults(handler=test_profile)


    subscription_parser = commands.add_parser("sub", help="Manage subscriptions")
    subscription_commands = subscription_parser.add_subparsers(dest="subscription_command", required=True)

    add_sub_parser = subscription_commands.add_parser("add", help="Add a subscription")
    add_sub_parser.add_argument("--name", help="Profile name", required=True)
    add_sub_parser.add_argument("--topic", help="Topic to subscribe to", required=True)
    add_sub_parser.add_argument(
        "--qos", type=int, choices=(0, 1, 2), default=1, help="QoS level"
    )
    add_sub_parser.add_argument(
        "--retain-as-published", action="store_true", help="Retain as published"
    )
    add_sub_parser.add_argument(
        "--retain-handling",
        type=int,
        choices=(0, 1, 2),
        default=0,
        help="Retain handling",
    )
    add_sub_parser.set_defaults(handler=add_subscription)

    add_sub_parser = subscription_commands.add_parser("remove", help="Remove a subscription")
    add_sub_parser.add_argument("--name", help="Profile name", required=True)
    add_sub_parser.add_argument("--topic", help="Topic to subscribe to", required=True)
    add_sub_parser.set_defaults(handler=remove_subscription)


    return parser

def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)
