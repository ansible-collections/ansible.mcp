from abc import ABC, abstractmethod


class Transport(ABC):
    @abstractmethod
    def connect(self) -> None:
        """Connect to the MCP server.

        This is called before attempting to perform initialization.
        """
        pass

    @abstractmethod
    def notify(self, data: dict) -> None:
        """Send a notification message to the server.

        This sends a JSON-RPC payload to the server when no response is
        expected.

        Args:
            data: JSON-RPC payload.
        """
        pass

    @abstractmethod
    def request(self, data: dict) -> dict:
        """Send a request to the server.

        This sends a JSON-RPC payload to the server when a response is expected.

        Args:
            data: JSON-RPC payload.
        Returns:
            The JSON-RPC response from the server.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the server connection.

        This is called to perform any final actions to close and clean up the
        connection.
        """
        pass
