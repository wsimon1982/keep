"""
ZulipProvider is a notification provider for Zulip.
API: https://zulip.com/api/send-message
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
class ZulipProviderAuthConfig:
    """Zulip authentication configuration."""

    url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip server URL (e.g., https://zulip.example.com)",
        }
    )
    bot_email: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip bot email address",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip bot API key",
            "sensitive": True,
        }
    )
    stream: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip stream name to send messages to",
        }
    )


class ZulipProvider(BaseProvider):
    """Send alert messages to Zulip streams via bot API."""

    PROVIDER_DISPLAY_NAME = "Zulip"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_LINK = "https://zulip.com/"
    PROVIDER_DESCRIPTION = "Send Keep alerts to Zulip streams via bot API"
    IS_TESTABLE = True

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ZulipProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """No cleanup needed."""
        pass

    def _notify(
        self,
        message: str = "",
        title: str = "",
        **kwargs: dict,
    ):
        """Send notification to Zulip stream."""
        self.logger.debug("Sending message to Zulip")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send message: message body is required"
            )

        topic = title if title else "KeepHQ Alert"
        display_message = message
        if title:
            display_message = f"**{title}**\n\n{message}"

        url = f"{self.authentication_config.url}/api/messages"

        payload = {
            "type": "stream",
            "to": self.authentication_config.stream,
            "subject": topic,
            "content": display_message,
        }

        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                auth=(self.authentication_config.bot_email, self.authentication_config.api_key),
                timeout=30,
            )

            if response.status_code != 200:
                error_msg = response.text
                raise ProviderException(
                    f"{self.__class__.__name__} failed to send Zulip message: "
                    f"HTTP {response.status_code} - {error_msg[:200]}"
                )

            self.logger.info(f"Message sent to Zulip stream {self.authentication_config.stream}")
            return True

        except requests.exceptions.ConnectionError as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to connect to Zulip: {str(e)}"
            )
        except requests.exceptions.Timeout:
            raise ProviderException(
                f"{self.__class__.__name__} connection to Zulip timed out"
            )
        except requests.exceptions.RequestException as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send Zulip message: {str(e)}"
            )

    def test(self):
        """Test the Zulip connection."""
        self.logger.debug("Testing Zulip connection")

        if not self.authentication_config:
            self.validate_config()

        url = f"{self.authentication_config.url}/api/messages"

        payload = {
            "type": "stream",
            "to": self.authentication_config.stream,
            "subject": "KeepHQ Test",
            "content": "KeepHQ test notification - connection successful!",
        }

        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                auth=(self.authentication_config.bot_email, self.authentication_config.api_key),
                timeout=30,
            )

            if response.status_code == 200:
                return {
                    "ok": True,
                    "message": "Zulip connection successful - test message sent",
                }
            elif response.status_code == 401:
                return {
                    "ok": False,
                    "message": "Zulip connection test failed: Invalid credentials (401 Unauthorized)",
                }
            else:
                return {
                    "ok": False,
                    "message": f"Zulip connection test failed: HTTP {response.status_code} - {response.text[:200]}",
                }

        except requests.exceptions.ConnectionError:
            return {
                "ok": False,
                "message": f"Cannot connect to Zulip server {self.authentication_config.url}",
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"Zulip connection test failed: {str(e)}",
            }
