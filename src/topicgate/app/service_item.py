from abc import ABC, abstractmethod


class ServiceItem(ABC):
    """A component whose lifetime is managed by the application."""

    @abstractmethod
    async def start(self) -> None:
        """Start the service."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the service."""
