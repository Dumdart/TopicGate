## Observe Smart Home Topics

`ObserverRepository` accepts a list of absolute MQTT topic filters. Filters are
passed to MQTT unchanged, including leading or trailing slashes and MQTT
wildcards such as `#` and `+`. `TopicService` supplies only the application's
optional convenience catalogue; applications may provide any filters directly.
Every received topic is retained in `ObserverModel.topic_states`, including
topics discovered through wildcard filters. Consumers can await normalized
`MqttMessage` instances from `ObserverRepository.message_queue`; the current
value map is updated before each message is queued.

``` bash 
python -m pip install -e .

smart-home-observer.exe
```
