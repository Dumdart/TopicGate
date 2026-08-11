from topicgate.app.topicgate_runtime import TopicGateRuntime


class SubscriptionAPI:
    def __init__(self, runtime: TopicGateRuntime):
        self._runtime = runtime
