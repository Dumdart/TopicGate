from smart_home_observer.core.models.observer_model import ObserverModel, TopicNode


class TopicService:
    """Provides the configured MQTT topic catalogue."""

    @staticmethod
    def get_topics() -> ObserverModel:
        return ObserverModel(
            root_stats=[
                TopicNode(
                    segment="SmartHome",
                    children={
                        "Huehnerstall": TopicNode(
                            segment="Huehnerstall",
                            children={
                                "door": TopicNode(
                                    segment="door",
                                    children={
                                        "command": TopicNode(segment="command"),
                                        "status": TopicNode(segment="status"),
                                        "status_code": TopicNode(segment="status_code"),
                                        "fault": TopicNode(segment="fault"),
                                        "connected": TopicNode(segment="connected"),
                                        "battery": TopicNode(segment="battery"),
                                        "light_level": TopicNode(segment="light_level"),
                                    },
                                )
                            }
                        )
                    },
                )
            ]
        )
