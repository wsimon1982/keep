"""
FlockProvider is a class that provides incoming webhook notification for Flock.
Flock is a team collaboration platform.

API: https://dev.flock.com/webhooks
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
class FlockProviderAuthConfig:
    """Flock authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Flock Webhook URL (e.g., https://api.flock.com/chat.send?token=YOUR_TOKEN)",
        }
    )

    channel: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Flock channel ID or user ID to send messages to",
            "hint": "Find channel ID in channel settings",
        }
    )


class FlockProvider(BaseProvider):
    """Send alert messages to Flock channels via incoming webhook."""

    PROVIDER_DISPLAY_NAME = "Flock"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_LINK = "https://flock.com/"
    PROVIDER_DESCRIPTION = "Send Keep alerts to Flock channels via incoming webhooks"
    IS_TESTABLE = True
    FLOCK_API = "https://api.flock.com"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FlockProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """No cleanup needed."""
        pass

    def _parse_webhook_url(self):
        """Parse the webhook URL to extract base URL and token."""
        url = self.authentication_config.webhook_url
        # Format: https://api.flock.com/chat.send?token=TOKEN
        if "?token=" in url:
            base_url = url.split("?")[0]
            token = url.split("token=")[1].split("&")[0]
        else:
            base_url = "https://api.flock.com/chat.send"
            token = ""
        return base_url, token

    def _notify(
        self,
        message: str = "",
        **kwargs: dict,
    ):
        """
        Send notification message to Flock channel.

        Args:
            message (str): Message body to send
        """
        self.logger.debug("Sending message to Flock channel")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send message: message body is required"
            )

        base_url, token = self._parse_webhook_url()

        payload = {
            "token": token,
            "channel": self.authentication_config.channel,
            "text": message,
            "type": "text",
        }

        try:
            response = requests.post(
                base_url,
                json=payload,
                timeout=30,
            )

            if response.status_code != 200:
                error_msg = response.text
                raise ProviderException(
                    f"{self.__class__.__name__} failed to send Flock message: "
                    f"HTTP {response.status_code} - {error_msg[:200]}"
                )

            result = response.json()
            if result.get("status") != 1:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to send Flock message: {result.get('error', 'Unknown error')}"
                )

            self.logger.info(f"Message sent to Flock channel {self.authentication_config.channel}")
            return True

        except requests.exceptions.ConnectionError as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to connect to Flock: {str(e)}"
            )
        except requests.exceptions.Timeout:
            raise ProviderException(
                f"{self.__class__.__name__} connection to Flock timed out"
            )
        except requests.exceptions.RequestException as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send Flock message: {str(e)}"
            )

    def test(self):
        """Test the Flock connection by sending a test message."""
        self.logger.debug("Testing Flock connection")

        if not self.authentication_config:
            self.validate_config()

        base_url, token = self._parse_webhook_url()

        payload = {
            "token": token,
            "channel": self.authentication_config.channel,
            "text": "KeepHQ test message - connection successful!",
            "type": "text",
        }

        try:
            response = requests.post(
                base_url,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == 1:
                    return {
                        "ok": True,
                        "message": "Flock connection successful - test message sent",
                    }
                else:
                    return {
                        "ok": False,
                        "message": f"Flock test failed: {result.get('error', 'Unknown error')}",
                    }
            else:
                return {
                    "ok": False,
                    "message": f"Flock connection test failed: HTTP {response.status_code} - {response.text[:200]}",
                }

        except requests.exceptions.ConnectionError:
            return {
                "ok": False,
                "message": "Cannot connect to Flock",
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"Flock connection test failed: {str(e)}",
            }
