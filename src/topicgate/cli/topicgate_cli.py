
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


def _profile_password(args: argparse.Namespace) -> str:
    if args.no_password and args.password_stdin:
        raise ValueError("--no-password and --password-stdin cannot be combined.")
    if args.no_password:
        return ""
    if args.password_stdin:
        password = sys.stdin.readline()
        if not password:
            raise ValueError("No MQTT password was provided on stdin.")
        return password.rstrip("\r\n")
    return getpass("MQTT password: ")


def add_profile(args: argparse.Namespace) -> int:
    dependencies = AppDependencies()

    try:
        profile = dependencies.broker_profiles.get_profile_by_name(args.name)
    except KeyError:
        pass
    else:
        print(f"Broker profile already exists: {profile.name}")
        return 0

    try:
        password = _profile_password(args)
    except ValueError as error:
        _print_error(error)
        return 1

    config = MqttConfig(
        username=args.username,
        host=args.host,
        port=args.port,
        password=password,
        use_tls=args.use_tls,
    )

    try:
        profile = dependencies.broker_profiles.create_profile(args.name, config)
        dependencies.broker_profiles.save()

    except (KeyError, ValueError) as error:
        _print_error(error)
        return 1

    print(f"Broker profile added: {profile.name}")
    return 0


def remove_profile(args: argparse.Namespace) -> int:
    dependencies = AppDependencies()

    try:
        profile = dependencies.broker_profiles.get_profile_by_name(args.name)
        dependencies.broker_profiles.delete_profile(profile.id)
    except (KeyError, ValueError) as error:
        _print_error(error)
        return 1

    print(f"Broker profile removed: {profile.name}")
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


def list_subscriptions(args: argparse.Namespace) -> int:
    dependencies = AppDependencies()

    try:
        profile = dependencies.broker_profiles.get_profile_by_name(args.name)
    except (KeyError, ValueError) as error:
        _print_error(error)
        return 1

    for subscription in profile.workspace.subscriptions:
        print(
            subscription.topic_filter,
            subscription.qos,
            subscription.retain_as_published,
            subscription.retain_handling,
            sep="\t",
        )
    return 0


def test_profile(args: argparse.Namespace) -> int:
    dependencies = AppDependencies()

    try:
        profiles = (
            (dependencies.broker_profiles.get_profile_by_name(args.name),)
            if args.name
            else dependencies.broker_profiles.get_all_profiles()
        )
        for profile in profiles:
            print(f"Testing profile: {profile.name}")
            dependencies.broker_profiles.test_profile(profile.id)
    except (KeyError, ConnectionError, TimeoutError, OSError) as error:
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
    profile_commands = profile_parser.add_subparsers(
        dest="profile_command", required=True
    )

    add_profile_parser = profile_commands.add_parser("add", help="Add a new profile")
    add_profile_parser.add_argument(
        "--name", help='Profile name (e.g. "MyBroker123")', required=True
    )
    add_profile_parser.add_argument(
        "--host", default="localhost", help="MQTT broker host"
    )
    add_profile_parser.add_argument(
        "--port", type=int, default=1883, help="MQTT broker port"
    )
    add_profile_parser.add_argument("--username", default="", help="MQTT username")
    add_profile_parser.add_argument("--use-tls", action="store_true", help="Use TLS")
    password_group = add_profile_parser.add_mutually_exclusive_group()
    password_group.add_argument(
        "--no-password", action="store_true", help="Use an empty MQTT password"
    )
    password_group.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the MQTT password from standard input",
    )
    add_profile_parser.set_defaults(handler=add_profile)

    list_profile_parser = profile_commands.add_parser("list", help="List all profiles")
    list_profile_parser.set_defaults(handler=list_profiles)

    test_profile_parser = profile_commands.add_parser(
        "test", help="Test profile connection"
    )
    test_profile_parser.add_argument("--name", help="Test only this profile")
    test_profile_parser.set_defaults(handler=test_profile)

    remove_profile_parser = profile_commands.add_parser(
        "remove", help="Remove a profile"
    )
    remove_profile_parser.add_argument("--name", help="Profile name", required=True)
    remove_profile_parser.set_defaults(handler=remove_profile)

    subscription_parser = commands.add_parser("sub", help="Manage subscriptions")
    subscription_commands = subscription_parser.add_subparsers(
        dest="subscription_command", required=True
    )

    list_sub_parser = subscription_commands.add_parser(
        "list", help="List subscriptions for a profile"
    )
    list_sub_parser.add_argument("--name", help="Profile name", required=True)
    list_sub_parser.set_defaults(handler=list_subscriptions)

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

    remove_sub_parser = subscription_commands.add_parser(
        "remove", help="Remove a subscription"
    )
    remove_sub_parser.add_argument("--name", help="Profile name", required=True)
    remove_sub_parser.add_argument(
        "--topic", help="Topic to unsubscribe from", required=True
    )
    remove_sub_parser.set_defaults(handler=remove_subscription)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)
