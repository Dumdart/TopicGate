## Observe Smart Home Topics

`ObserverRepository` accepts a list of absolute MQTT topic filters. Filters are
passed to MQTT unchanged, including leading or trailing slashes and MQTT
wildcards such as `#` and `+`. `TopicService` supplies only the application's
optional convenience catalogue; applications may provide any filters directly.

``` bash 
python -m pip install -e .

smart-home-observer.exe
```
