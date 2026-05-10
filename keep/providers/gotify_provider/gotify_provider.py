"""
GotifyProvider is an interface for sending push notifications via Gotify.
Gotify is a self-hosted push notification server.

API: https://gotify.net/docs/pushmsg
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
class GotifyProviderAuthConfig:
    """Gotify authentication configuration."""

    server_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Gotify server URL (e.g., https://gotify.example.com)",
        }
    )

    token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Gotify application token",
            "sensitive": True,
        }
    )


class GotifyProvider(BaseProvider):
    """Send push notifications via Gotify."""

    PROVIDER_DISPLAY_NAME = "Gotify"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_LINK = "https://gotify.net/"
    PROVIDER_DESCRIPTION = "Send Keep alerts via Gotify push notifications"
    IS_TESTABLE = True

    GOTIFY_API = "https://gotify.net/docs/pushmsg"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GotifyProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """No cleanup needed."""
        pass

    def _notify(
        self,
        message: str = "",
        title: str = "",
        priority: int = 0,
        **kwargs: dict,
    ):
        """
        Send notification via Gotify.

        Args:
            message (str): Message body to send
            title (str): Message title (defaults to alert name)
            priority (int): Message priority (0-10), defaults to 0
        """
        self.logger.debug("Sending message to Gotify")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send message: message body is required"
            )

        url = f"{self.authentication_config.server_url}/message?token={self.authentication_config.token}"

        body = {
            "message": message,
            "priority": priority,
        }
        if title:
            body["title"] = title

        try:
            response = requests.post(
                url,
                json=body,
                timeout=30,
            )

            if response.status_code not in (200, 201):
                error_msg = response.text
                raise ProviderException(
                    f"{self.__class__.__name__} failed to send Gotify message: "
                    f"HTTP {response.status_code} - {error_msg[:200]}"
                )

            self.logger.info(f"Message sent to Gotify successfully")
            return True

        except requests.exceptions.ConnectionError as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to connect to Gotify server: {str(e)}"
            )
        except requests.exceptions.Timeout:
            raise ProviderException(
                f"{self.__class__.__name__} connection to Gotify timed out"
            )
        except requests.exceptions.RequestException as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send Gotify message: {str(e)}"
            )

    def test(self):
        """Test the Gotify connection by posting a test message."""
        self.logger.debug("Testing Gotify connection")

        if not self.authentication_config:
            self.validate_config()

        url = f"{self.authentication_config.server_url}/message?token={self.authentication_config.token}"

        body = {
            "message": "KeepHQ test notification - connection successful!",
            "title": "KeepHQ Test",
            "priority": 0,
        }

        try:
            response = requests.post(
                url,
                json=body,
                timeout=30,
            )

            if response.status_code in (200, 201):
                return {
                    "ok": True,
                    "message": "Gotify connection successful - test message sent",
                }
            elif response.status_code == 401:
                return {
                    "ok": False,
                    "message": "Gotify connection test failed: Invalid token (401 Unauthorized)",
                }
            else:
                return {
                    "ok": False,
                    "message": f"Gotify connection test failed: HTTP {response.status_code} - {response.text[:200]}",
                }

        except requests.exceptions.ConnectionError:
            return {
                "ok": False,
                "message": f"Cannot connect to Gotify server {self.authentication_config.server_url}",
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"Gotify connection test failed: {str(e)}",
            }
