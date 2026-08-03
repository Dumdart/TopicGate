from abc import ABC, abstractmethod


class ServiceItem(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def start():
        pass

    @abstractmethod
    def stop():
        pass
