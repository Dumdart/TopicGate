from smart_home_observer.core.models.observer_model import ObserverModel, TopicNode
from smart_home_observer.services.observer_model_service import ObserverModelService


class TopicService:
    """Provides an optional convenience catalogue of MQTT topic filters."""

    @staticmethod
    def get_topic_filters() -> list[str]:
        """Return the catalogue's absolute MQTT filters."""
        return ObserverModelService.get_all_topics(TopicService.get_topics())

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
