import json

from abc import ABC, abstractmethod
from typing import Optional

from ansible.module_utils.urls import open_url


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


class StreamableHTTP(Transport):
    def __init__(self, url: str, headers: Optional[dict] = None):
        """Initialize the StreamableHTTP transport.

        Args:
            url: The MCP server URL endpoint
            headers: Optional headers to include with requests
            session_id: Optional session ID to include with requests
        """
        self.url = url
        self.headers = headers or {}
        self.session_id = None

    def connect(self) -> None:
        """Connect to the MCP server.

        For HTTP transport, this is a no-op as connection is established
        per-request.
        """
        pass

    def notify(self, data: dict) -> None:
        """Send a notification message to the server.

        Args:
            data: JSON-RPC payload.
        """
        headers = self._build_headers()

        try:
            response = open_url(
                self.url,
                method="POST",
                data=json.dumps(data),
                headers=headers,
                validate_certs=False,
            )

            self._extract_session_id(response)

            if response.getcode() != 202:
                raise Exception(f"Unexpected response code: {response.getcode()}")

        except Exception as e:
            raise Exception(f"Failed to send notification: {str(e)}")

    def request(self, data: dict) -> dict:
        """Send a request to the server.

        Args:
            data: JSON-RPC payload.

        Returns:
            The JSON-RPC response from the server.
        """
        headers = self._build_headers()

        try:
            response = open_url(
                self.url,
                method="POST",
                data=json.dumps(data),
                headers=headers,
                validate_certs=False,
            )

            self._extract_session_id(response)

            response_data = response.read()

            if response.getcode() != 200:
                raise Exception(f"Unexpected response code: {response.getcode()}")

            # Parse JSON response
            try:
                return json.loads(response_data.decode("utf-8"))
            except json.JSONDecodeError as e:
                raise Exception(f"Invalid JSON response: {str(e)}")

        except Exception as e:
            raise Exception(f"Failed to send request: {str(e)}")

    def close(self) -> None:
        """Close the server connection.

        For HTTP transport, this is a no-op as connections are not persistent.
        """
        pass

    def _build_headers(self) -> dict:
        """Build headers for HTTP requests.

        Returns:
            Dictionary of headers to include in the request.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-06-18",
        }

        # Add custom headers
        headers.update(self.headers)

        # Add session ID if available
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        return headers

    def _extract_session_id(self, response) -> None:
        """Extract session ID from response headers.

        Args:
            response: The HTTP response object
        """
        # Check for Mcp-Session-Id header in response
        session_header = response.headers.get("Mcp-Session-Id")
        if session_header is not None:
            self.session_id = session_header
