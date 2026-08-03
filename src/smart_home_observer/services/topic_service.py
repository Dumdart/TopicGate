from smart_home_observer.core.models.observer_model import ObserverModel, TopicNode


class TopicService:
    """Provides the configured MQTT topic catalogue."""

    @staticmethod
    def get_topics() -> ObserverModel:
        return ObserverModel(
            root_stats=[
                TopicNode(
                    segment="home",
                    children={
                        "chicken-door": TopicNode(
                            segment="chicken-door",
                            children={
                                "command": TopicNode(segment="command"),
                                "status": TopicNode(segment="status"),
                                "status_code": TopicNode(segment="status_code"),
                                "fault": TopicNode(segment="fault"),
                                "connected": TopicNode(segment="connected"),
                                "battery": TopicNode(segment="battery"),
                                "light_level": TopicNode(segment="light_level"),
                            },
                        ),
                        "weather-station": TopicNode(
                            segment="weather-station",
                            children={
                                "temperature": TopicNode(segment="temperature"),
                                "humidity": TopicNode(segment="humidity"),
                                "pressure": TopicNode(segment="pressure"),
                                "battery": TopicNode(segment="battery"),
                                "connected": TopicNode(segment="connected"),
                            },
                        ),
                    },
                )
            ]
        )
