"""
MatrixProvider is an interface for sending alerts to Matrix rooms.
Matrix is an open decentralized communication protocol.

API: https://spec.matrix.org/v1.6/client-server-api/
"""

import dataclasses
from typing import Optional

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MatrixProviderAuthConfig:
    """Matrix authentication configuration."""

    server_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix server URL (e.g., https://matrix.org)",
        }
    )

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix access token (from login or client)",
            "sensitive": True,
        }
    )

    room_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix room ID to send messages to (e.g., !abc123:matrix.org)",
        }
    )


class MatrixProvider(BaseProvider):
    """Send alert messages to Matrix rooms."""

    PROVIDER_DISPLAY_NAME = "Matrix"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_LINK = "https://matrix.org/"
    PROVIDER_DESCRIPTION = "Send Keep alerts to Matrix rooms (Element, Synapse, etc.)"
    IS_TESTABLE = True

    MATRIX_API = "https://spec.matrix.org/v1.6/client-server-api/"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MatrixProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """No cleanup needed."""
        pass

    def _get_headers(self):
        """Get request headers with auth token."""
        return {
            "Authorization": f"Bearer {self.authentication_config.access_token}",
            "Content-Type": "application/json",
        }

    def _notify(
        self,
        message: str = "",
        msgtype: str = "m.text",
        **kwargs: dict,
    ):
        """
        Send notification message to Matrix room.

        Args:
            message (str): Message body to send
            msgtype (str): Message type, defaults to "m.text"
        """
        self.logger.debug("Sending message to Matrix room")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send message: message body is required"
            )

        url = f"{self.authentication_config.server_url}/_matrix/client/v3/rooms/{self.authentication_config.room_id}/send/{msgtype}"

        body = {
            "body": message,
            "msgtype": msgtype,
        }

        if msgtype == "m.html" and kwargs.get("formatted_body"):
            body["format"] = "org.matrix.html"
            body["format_body"] = kwargs.get("formatted_body")

        try:
            response = requests.post(
                url,
                json=body,
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code != 200:
                error_msg = response.text
                raise ProviderException(
                    f"{self.__class__.__name__} failed to send Matrix message: "
                    f"HTTP {response.status_code} - {error_msg[:200]}"
                )

            result = response.json()
            self.logger.info(
                f"Message sent to Matrix room {self.authentication_config.room_id}, event_id: {result.get('event_id')}"
            )
            return True

        except requests.exceptions.ConnectionError as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to connect to Matrix server {self.authentication_config.server_url}: {str(e)}"
            )
        except requests.exceptions.Timeout:
            raise ProviderException(
                f"{self.__class__.__name__} connection to Matrix server timed out"
            )
        except requests.exceptions.RequestException as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send Matrix message: {str(e)}"
            )

    def test(self):
        """Test the Matrix connection by verifying auth token."""
        self.logger.debug("Testing Matrix connection")

        if not self.authentication_config:
            self.validate_config()

        # Try /whoami first, then /sync as fallback
        # Matrix servers vary - /whoami works on Synapse, some on /sync
        whoami_url = f"{self.authentication_config.server_url}/_matrix/client/r0/whoami"
        sync_url = f"{self.authentication_config.server_url}/_matrix/client/r0/sync"

        for test_url, test_name in [(whoami_url, "/whoami"), (sync_url, "/sync")]:
            try:
                response = requests.get(
                    test_url,
                    headers=self._get_headers(),
                    timeout=30,
                )

                if response.status_code == 200:
                    if test_name == "/whoami":
                        user_info = response.json()
                        user_id = user_info.get('user_id', 'unknown')
                        return {
                            "ok": True,
                            "message": f"Matrix connection successful - user: {user_id}",
                        }
                    elif test_name == "/sync":
                        # /sync 200 means valid auth (even with empty rooms)
                        return {
                            "ok": True,
                            "message": "Matrix connection successful",
                        }
                elif response.status_code == 401:
                    return {
                        "ok": False,
                        "message": "Matrix connection test failed: Invalid access token (401 Unauthorized)",
                    }
                # Try next endpoint
            except requests.exceptions.ConnectionError:
                if test_name == "/sync":
                    return {
                        "ok": False,
                        "message": f"Cannot connect to Matrix server {self.authentication_config.server_url}",
                    }
                continue
            except Exception as e:
                if test_name == "/sync":
                    return {
                        "ok": False,
                        "message": f"Matrix connection test failed: {str(e)}",
                    }
                continue

        return {
            "ok": False,
            "message": "Matrix connection test failed: Server does not respond to auth checks",
        }
