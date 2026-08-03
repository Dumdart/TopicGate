from smart_home_observer.services.topic_service import TopicService


def test_topic_service_provides_chicken_door_topic_tree() -> None:
    model = TopicService.get_topics()

    home = model.root_stats[0]
    chicken_door = home.children["chicken-door"]

    assert home.segment == "home"
    assert set(chicken_door.children) == {
        "command",
        "status",
        "status_code",
        "fault",
        "connected",
        "battery",
        "light_level",
    }


def test_topic_service_provides_a_separate_weather_station_branch() -> None:
    model = TopicService.get_topics()

    weather_station = model.root_stats[0].children["weather-station"]

    assert set(weather_station.children) == {
        "temperature",
        "humidity",
        "pressure",
        "battery",
        "connected",
    }
