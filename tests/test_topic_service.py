from smart_home_observer.services.topic_service import TopicService


def test_topic_service_provides_chicken_door_topic_tree() -> None:
    model = TopicService.get_topics()

    smart_home = model.root_stats[0]
    chicken_door = smart_home.children["Huehnerstall"].children["door"]

    assert smart_home.segment == "SmartHome"
    assert set(chicken_door.children) == {
        "command",
        "status",
        "status_code",
        "fault",
        "connected",
        "battery",
        "light_level",
    }


def test_topic_service_contains_only_the_configured_chicken_door_branch() -> None:
    model = TopicService.get_topics()

    assert set(model.root_stats[0].children) == {"Huehnerstall"}
