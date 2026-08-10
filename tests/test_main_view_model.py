import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import UUID, uuid4

from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.broker_profile import BrokerProfile
from topicgate.core.models.observer_model import (
    ObserverModel,
    TopicNode,
    TopicState,
)
from topicgate.core.models.observer_workspace import ObserverWorkspace
from topicgate.core.models.subscription import Subscription
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.gui.main_view_model import MainViewModel, mqtt_filter_matches
from topicgate.core.payload_limits import (
    MAX_FORMATTED_JSON_CHARACTERS,
    MAX_RENDERED_PAYLOAD_BYTES,
)


class FakeObserverRepository:
    topic_update_interval = 0.0
    connection_status = "disconnected"

    def __init__(self) -> None:
        self._states: dict[str, TopicState] = {}
        self._messages: asyncio.Queue[MqttMessage] = asyncio.Queue()
        self.subscriptions: tuple[Subscription, ...] = ()
        self.connection_operations: list[str] = []
        self.removed_subscriptions: list[Subscription] = []
        self.broker_configurations: list[MqttConfig] = []
        self.dropped_message_count = 0

    async def start(self) -> None:
        self.connection_status = "connected"

    async def stop(self) -> None:
        self.connection_status = "disconnected"

    def get(self) -> ObserverModel:
        return ObserverModel(root_stats=[], topic_states=dict(self._states))

    def get_state(self, topic: str) -> TopicState | None:
        return self._states.get(topic)

    async def messages(self) -> AsyncIterator[MqttMessage]:
        while True:
            yield await self._messages.get()

    async def connection_statuses(self) -> AsyncIterator[object]:
        if False:
            yield "disconnected"

    def drain_pending_messages(self) -> tuple[MqttMessage, ...]:
        messages: list[MqttMessage] = []
        while not self._messages.empty():
            messages.append(self._messages.get_nowait())
        return tuple(messages)

    def publish(self, message: MqttMessage) -> None:
        self._states[message.topic] = TopicState(
            name=message.topic.rsplit("/", maxsplit=1)[-1],
            topic=message.topic,
            payload=message.payload,
            qos=message.qos,
            retain=message.retain,
            recieved_at=datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc),
        )
        self._messages.put_nowait(message)

    async def connect(self) -> None:
        self.connection_operations.append("connect")

    async def reconnect(self) -> None:
        self.connection_operations.append("reconnect")

    async def disconnect(self) -> None:
        self.connection_operations.append("disconnect")

    async def update_broker(
        self,
        new_config: MqttConfig,
        model: ObserverModel | None = None,
        subscriptions: tuple[Subscription, ...] | None = None,
    ) -> None:
        self.broker_configurations.append(new_config)
        if model is not None:
            self._states = model.topic_states
        if subscriptions is not None:
            self.subscriptions = subscriptions

    async def remove_subscription(self, subscription: Subscription) -> None:
        self.removed_subscriptions.append(subscription)
        self.subscriptions = tuple(
            item for item in self.subscriptions if item != subscription
        )

    async def add_subscription(self, subscription: Subscription) -> None:
        self.subscriptions += (subscription,)

    async def update_subscription(
        self, original_filter: str, subscription: Subscription
    ) -> None:
        self.subscriptions = tuple(
            subscription if item.topic_filter == original_filter else item
            for item in self.subscriptions
        )


class FakeBrokerRepository:
    def __init__(self, mqtt: MqttConfig) -> None:
        default_profile = self._profile("Default", mqtt)
        local_profile = self._profile("Local MQTT", MqttConfig("localhost", 1883, "", ""))
        self._profiles = {
            default_profile.id: default_profile,
            local_profile.id: local_profile,
        }
        self._active_profile_id = default_profile.id
        self.updated_mqtt: list[MqttConfig] = []

    def get_mqtt(self) -> MqttConfig:
        return self.get_profile().config

    def update_mqtt(self, mqtt: MqttConfig) -> None:
        self.activate_profile(self._active_profile_id, mqtt)

    def get_profile(self, profile_id: UUID | None = None) -> BrokerProfile:
        return self._profiles[profile_id or self._active_profile_id]

    def get_all_profiles(self) -> tuple[BrokerProfile, ...]:
        return tuple(self._profiles.values())

    def create_profile(self, name: str, mqtt: MqttConfig) -> BrokerProfile:
        profile = self._profile(name.strip(), mqtt)
        self._profiles[profile.id] = profile
        return profile

    def update_profile(self, profile: BrokerProfile) -> None:
        self._profiles[profile.id] = profile

    def delete_profile(self, profile_id: UUID) -> BrokerProfile:
        return self._profiles.pop(profile_id)

    def activate_profile(self, profile_id: UUID, mqtt: MqttConfig | None = None) -> None:
        profile = self.get_profile(profile_id)
        if mqtt is not None:
            profile.config = mqtt
            self.updated_mqtt.append(mqtt)
        self._active_profile_id = profile_id

    def update_observer_workspace(self, workspace: ObserverWorkspace) -> None:
        self._profiles[workspace.profile_id].workspace = workspace

    def update_observer_model(self, model: ObserverModel) -> None:
        self.get_profile().workspace.model = model

    @staticmethod
    def _profile(name: str, mqtt: MqttConfig) -> BrokerProfile:
        profile_id = uuid4()
        workspace = ObserverWorkspace(
            id=uuid4(),
            profile_id=profile_id,
            model=ObserverModel(root_stats=[]),
        )
        return BrokerProfile(profile_id, name, mqtt, workspace.id, workspace)


class FakeTopicGateRuntime(TopicGateRuntime):
    """Runtime test double backed by in-memory repositories."""


def runtime_for(
    repository: FakeObserverRepository,
    broker_repository: FakeBrokerRepository | None = None,
) -> FakeTopicGateRuntime:
    brokers = broker_repository or FakeBrokerRepository(
        MqttConfig("default", 1883, "", "")
    )
    return FakeTopicGateRuntime(brokers, repository)


def test_view_model_displays_and_refreshes_the_selected_topic_state() -> None:
    async def scenario() -> None:
        topic = "SmartHome/Huehnerstall/door/status"
        repository = FakeObserverRepository()
        view_model = MainViewModel(runtime_for(repository), topic)

        assert view_model.value == "Waiting for a message"

        await view_model.start()
        repository.publish(MqttMessage(topic, b"open", qos=1, retain=True))
        await asyncio.sleep(0)

        assert view_model.topic == topic
        assert view_model.value == "open"
        assert view_model.quality_of_service == "1"
        assert view_model.retained == "True"
        assert view_model.received_at == "2026-08-04T12:00:00+00:00"

        await view_model.stop()

    asyncio.run(scenario())


def test_view_model_batches_notifications_and_reports_dropped_messages() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        repository.dropped_message_count = 4
        view_model = MainViewModel(runtime_for(repository), "untrusted/topic")
        logs: list[str] = []
        view_model.log_message.connect(logs.append)

        for index in range(3):
            repository.publish(
                MqttMessage(
                    "untrusted/topic", str(index).encode(), 0, False
                )
            )

        await view_model.start()
        await asyncio.sleep(0)
        await view_model.stop()

        assert view_model.value == "2"
        assert view_model.dropped_message_count == "4"
        assert logs == [
            "Received 3 MQTT messages (latest: untrusted/topic)",
            "Dropped 4 MQTT messages during admission (4 total)",
        ]

    asyncio.run(scenario())


def test_view_model_throttles_topic_tree_updates() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        repository.topic_update_interval = 0.02
        view_model = MainViewModel(runtime_for(repository), "untrusted/topic")
        state_changes: list[bool] = []
        topic_changes: list[bool] = []
        view_model.state_changed.connect(lambda: state_changes.append(True))
        view_model.topics_changed.connect(lambda: topic_changes.append(True))
        await view_model.start()
        state_changes.clear()
        topic_changes.clear()

        repository.publish(MqttMessage("untrusted/topic", b"value", 0, False))
        await asyncio.sleep(0)

        assert state_changes == []
        assert topic_changes == []

        await asyncio.sleep(0.03)
        assert state_changes == [True]
        assert topic_changes == [True]
        await view_model.stop()

    asyncio.run(scenario())


def test_discovered_topic_updates_details_and_only_matching_filter_is_editable() -> None:
    repository = FakeObserverRepository()
    repository.subscriptions = (Subscription("SmartHome/+/status", qos=2),)
    repository.publish(MqttMessage("SmartHome/kitchen/status", b"open", 1, False))
    repository.publish(MqttMessage("Other/device/value", b"42", 0, False))
    view_model = MainViewModel(runtime_for(repository))

    view_model.select_topic("SmartHome/kitchen/status")

    assert view_model.decoded_payload == "open"
    assert view_model.selected_subscription == repository.subscriptions[0]

    view_model.select_topic("Other/device/value")

    assert view_model.decoded_payload == "42"
    assert view_model.selected_subscription is None


def test_payload_rendering_is_bounded_and_reports_truncation() -> None:
    repository = FakeObserverRepository()
    payload = b'"' + b"x" * (MAX_RENDERED_PAYLOAD_BYTES + 100) + b'"'
    repository.publish(MqttMessage("untrusted/topic", payload, 0, False))
    view_model = MainViewModel(runtime_for(repository), "untrusted/topic")
    view_model.refresh()

    notice = (
        f"[Payload truncated: showing {MAX_RENDERED_PAYLOAD_BYTES} of "
        f"{len(payload)} bytes]"
    )
    assert view_model.decoded_payload.endswith(notice)
    assert len(view_model.decoded_payload) < MAX_RENDERED_PAYLOAD_BYTES + 100
    assert view_model.raw_payload.endswith(notice)
    assert len(view_model.raw_payload) < MAX_RENDERED_PAYLOAD_BYTES * 3 + 100


def test_small_json_payload_is_still_pretty_printed() -> None:
    repository = FakeObserverRepository()
    repository.publish(MqttMessage("trusted/topic", b'{"open":true}', 0, False))
    view_model = MainViewModel(runtime_for(repository), "trusted/topic")
    view_model.refresh()

    assert view_model.decoded_payload == '{\n  "open": true\n}'


def test_size_amplified_json_formatting_is_bounded() -> None:
    repository = FakeObserverRepository()
    payload = ("[" * 500 + "0" + "]" * 500).encode()
    repository.publish(MqttMessage("untrusted/json", payload, 0, False))
    view_model = MainViewModel(runtime_for(repository), "untrusted/json")
    view_model.refresh()

    assert view_model.decoded_payload.endswith("[Formatted JSON truncated]")
    assert len(view_model.decoded_payload) < MAX_FORMATTED_JSON_CHARACTERS + 100


def test_topic_paths_include_configured_filters_and_discovered_topics() -> None:
    repository = FakeObserverRepository()
    repository.subscriptions = (Subscription("SmartHome/#"),)
    repository.publish(MqttMessage("SmartHome/kitchen/temperature", b"21", 0, False))

    assert MainViewModel(runtime_for(repository)).topic_paths == [
        "SmartHome/#",
        "SmartHome/kitchen/temperature",
    ]


def test_topic_paths_exclude_discovered_topics_without_an_active_filter() -> None:
    repository = FakeObserverRepository()
    repository.subscriptions = (Subscription("SmartHome/#"),)
    repository.publish(MqttMessage("SmartHome/kitchen/status", b"open", 1, False))
    repository.publish(MqttMessage("Other/device/status", b"open", 1, False))

    assert MainViewModel(runtime_for(repository)).topic_paths == [
        "SmartHome/#",
        "SmartHome/kitchen/status",
    ]


def test_mqtt_filter_matching_supports_wildcards_and_system_topic_rules() -> None:
    assert mqtt_filter_matches("home/+/temperature", "home/kitchen/temperature")
    assert mqtt_filter_matches("home/#", "home/kitchen/temperature")
    assert mqtt_filter_matches("home/#", "home")
    assert not mqtt_filter_matches("home/+/temperature", "home/temperature")
    assert not mqtt_filter_matches("#", "$SYS/broker/uptime")
    assert mqtt_filter_matches("$SYS/#", "$SYS/broker/uptime")


def test_connection_commands_are_forwarded_to_the_repository() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        view_model = MainViewModel(runtime_for(repository))

        await view_model.connect_to_broker()
        await view_model.reconnect_to_broker()
        await view_model.disconnect_from_broker()

        assert repository.connection_operations == [
            "connect",
            "reconnect",
            "disconnect",
        ]

    asyncio.run(scenario())


def test_mqtt_configuration_is_applied_then_stored() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        initial = MqttConfig("old", 1883, "", "")
        broker_repository = FakeBrokerRepository(initial)
        view_model = MainViewModel(runtime_for(repository, broker_repository))
        replacement = MqttConfig("new", 8883, "observer", "password", True)
        logs: list[str] = []
        changes: list[bool] = []
        view_model.log_message.connect(logs.append)
        view_model.configuration_changed.connect(lambda: changes.append(True))

        await view_model.update_mqtt_config(replacement)

        assert view_model.mqtt_config == replacement
        assert repository.broker_configurations == [replacement]
        assert broker_repository.updated_mqtt == [replacement]
        assert changes == [True]
        assert logs == [
            "Connecting to MQTT broker: new:8883",
            "Updated MQTT broker: new:8883",
        ]

    asyncio.run(scenario())


def test_switching_broker_profile_activates_its_workspace_after_connecting() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        broker_repository = FakeBrokerRepository(MqttConfig("default", 1883, "", ""))
        view_model = MainViewModel(runtime_for(repository, broker_repository))
        local_profile = broker_repository.get_all_profiles()[1]

        await view_model.update_broker_profile(local_profile.id, local_profile.config)

        assert repository.broker_configurations == [local_profile.config]
        assert view_model.active_broker_profile.id == local_profile.id
        assert view_model.mqtt_config == local_profile.config

    asyncio.run(scenario())


def test_saving_inactive_broker_profile_does_not_connect_or_activate_it() -> None:
    repository = FakeObserverRepository()
    broker_repository = FakeBrokerRepository(MqttConfig("default", 1883, "", ""))
    view_model = MainViewModel(runtime_for(repository, broker_repository))
    active_profile = broker_repository.get_profile()
    inactive_profile = broker_repository.get_all_profiles()[1]
    replacement = MqttConfig("fixed", 8883, "observer", "secret", True)

    saved = view_model.save_broker_profile(
        inactive_profile.id,
        replacement,
        "Fixed local",
    )

    assert repository.broker_configurations == []
    assert broker_repository.get_profile().id == active_profile.id
    assert broker_repository.updated_mqtt == []
    assert saved.name == "Fixed local"
    assert saved.config == replacement


def test_profile_operations_allow_credentials_without_tls() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        broker_repository = FakeBrokerRepository(
            MqttConfig("default", 1883, "", "")
        )
        view_model = MainViewModel(runtime_for(repository, broker_repository))
        profile = broker_repository.get_profile()
        insecure = MqttConfig("broker", 1883, "observer", "secret")

        saved = view_model.save_broker_profile(profile.id, insecure)
        created = view_model.create_broker_profile("Plain MQTT", insecure)
        await view_model.activate_broker_profile(profile.id, insecure)

        assert saved.config == insecure
        assert created.config == insecure
        assert broker_repository.get_profile().config == insecure
        assert len(broker_repository.get_all_profiles()) == 3
        assert repository.broker_configurations == [insecure]

    asyncio.run(scenario())


def test_switching_broker_profile_replaces_the_visible_workspace_tree() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        broker_repository = FakeBrokerRepository(
            MqttConfig("default", 1883, "", "")
        )
        default_profile, local_profile = broker_repository.get_all_profiles()
        default_profile.workspace.model = ObserverModel(
            root_stats=[
                TopicNode(
                    "home",
                    children={"status": TopicNode("status")},
                )
            ]
        )
        default_profile.workspace.subscriptions = (Subscription("home/status"),)
        repository.subscriptions = default_profile.workspace.subscriptions
        local_profile.workspace.model = ObserverModel(
            root_stats=[
                TopicNode(
                    "bridge",
                    children={"connected": TopicNode("connected")},
                )
            ]
        )
        local_profile.workspace.subscriptions = (
            Subscription("bridge/connected"),
        )
        view_model = MainViewModel(runtime_for(repository, broker_repository))

        assert view_model.topic_paths == ["home/status"]

        await view_model.update_broker_profile(
            local_profile.id,
            local_profile.config,
        )

        assert view_model.topic_paths == ["bridge/connected"]
        assert repository.subscriptions == (Subscription("bridge/connected"),)

    asyncio.run(scenario())


def test_view_model_creates_and_renames_broker_profiles() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        broker_repository = FakeBrokerRepository(MqttConfig("default", 1883, "", ""))
        view_model = MainViewModel(runtime_for(repository, broker_repository))
        changes: list[bool] = []
        logs: list[str] = []
        view_model.configuration_changed.connect(lambda: changes.append(True))
        view_model.log_message.connect(logs.append)

        created = view_model.create_broker_profile(
            "Remote",
            MqttConfig("remote", 1883, "", ""),
        )
        await view_model.update_broker_profile(
            created.id,
            MqttConfig("remote-new", 8883, "user", "secret", True),
            "Remote TLS",
        )

        assert view_model.active_broker_profile.name == "Remote TLS"
        assert view_model.active_broker_profile.config.host == "remote-new"
        assert changes == [True, True]
        assert logs[0] == "Created broker profile: Remote"

    asyncio.run(scenario())


def test_deleting_active_profile_switches_before_removing_it() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        broker_repository = FakeBrokerRepository(MqttConfig("default", 1883, "", ""))
        view_model = MainViewModel(runtime_for(repository, broker_repository))
        deleted_profile = view_model.active_broker_profile
        replacement = view_model.broker_profiles[1]

        await view_model.delete_broker_profile(deleted_profile.id)

        assert view_model.active_broker_profile.id == replacement.id
        assert deleted_profile not in view_model.broker_profiles
        assert repository.broker_configurations == [replacement.config]

    asyncio.run(scenario())


def test_failed_mqtt_configuration_is_not_stored() -> None:
    class FailingObserverRepository(FakeObserverRepository):
        async def update_broker(
            self,
            new_config: MqttConfig,
            model: ObserverModel | None = None,
            subscriptions: tuple[Subscription, ...] | None = None,
        ) -> None:
            raise ConnectionError("broker unavailable")

    async def scenario() -> None:
        initial = MqttConfig("old", 1883, "", "")
        broker_repository = FakeBrokerRepository(initial)
        view_model = MainViewModel(runtime_for(FailingObserverRepository(), broker_repository))
        logs: list[str] = []
        view_model.log_message.connect(logs.append)

        try:
            await view_model.update_mqtt_config(MqttConfig("new", 8883, "", ""))
        except ConnectionError:
            pass
        else:
            raise AssertionError("Expected the broker update to fail")

        assert view_model.mqtt_config == initial
        assert broker_repository.updated_mqtt == []
        assert logs == [
            "Connecting to MQTT broker: new:8883",
            "Broker update failed: broker unavailable",
        ]

    asyncio.run(scenario())


def test_removing_subscription_updates_topics_and_clears_stale_selection() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        subscription = Subscription("SmartHome/#")
        repository.subscriptions = (subscription,)
        view_model = MainViewModel(
            runtime_for(repository), subscription.topic_filter
        )
        changed: list[str] = []
        logs: list[str] = []
        view_model.state_changed.connect(lambda: changed.append("state"))
        view_model.topics_changed.connect(lambda: changed.append("topics"))
        view_model.subscriptions_changed.connect(
            lambda: changed.append("subscriptions")
        )
        view_model.log_message.connect(logs.append)

        await view_model.remove_subscription(subscription)

        assert repository.removed_subscriptions == [subscription]
        assert repository.subscriptions == ()
        assert view_model.topic == ""
        assert changed == ["state", "topics", "subscriptions"]
        assert logs == ["Removed subscription: SmartHome/#"]

    asyncio.run(scenario())


def test_removing_subscription_hides_its_cached_topic_and_clears_selection() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        subscription = Subscription("SmartHome/kitchen/status")
        repository.subscriptions = (subscription,)
        repository.publish(
            MqttMessage(subscription.topic_filter, b"open", 1, False)
        )
        view_model = MainViewModel(
            runtime_for(repository), subscription.topic_filter
        )

        await view_model.remove_subscription(subscription)

        assert view_model.topic == ""
        assert view_model.topic_paths == []

    asyncio.run(scenario())


def test_removing_subscription_hides_cached_topic_from_observer_model() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        subscription = Subscription("SmartHome/kitchen/status")
        repository.subscriptions = (subscription,)
        broker_repository = FakeBrokerRepository(
            MqttConfig("default", 1883, "", "")
        )
        profile = broker_repository.get_profile()
        profile.workspace.model = ObserverModel(
            root_stats=[
                TopicNode(
                    segment="SmartHome",
                    children={
                        "kitchen": TopicNode(
                            segment="kitchen",
                            children={"status": TopicNode(segment="status")},
                        )
                    },
                )
            ]
        )
        view_model = MainViewModel(
            runtime_for(repository, broker_repository),
            subscription.topic_filter,
        )

        await view_model.remove_subscription(subscription)

        assert view_model.topic == ""
        assert view_model.topic_paths == []

    asyncio.run(scenario())


def test_removing_subscription_keeps_topics_covered_by_another_filter() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        removed = Subscription("SmartHome/kitchen/status")
        remaining = Subscription("SmartHome/#")
        repository.subscriptions = (removed, remaining)
        repository.publish(MqttMessage(removed.topic_filter, b"open", 1, False))
        view_model = MainViewModel(runtime_for(repository), removed.topic_filter)

        await view_model.remove_subscription(removed)

        assert view_model.topic == removed.topic_filter
        assert view_model.topic_paths == [
            remaining.topic_filter,
            removed.topic_filter,
        ]

    asyncio.run(scenario())
