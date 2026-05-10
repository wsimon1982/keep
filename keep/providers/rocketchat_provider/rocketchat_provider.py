"""
RocketChatProvider is a notification provider for Rocket.Chat.
API: https://developer.rocket.chat/docs/incoming-webhooks
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
class RocketChatProviderAuthConfig:
    """Rocket.Chat authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Rocket.Chat Incoming Webhook URL (e.g., https://open.rocket.chat/hooks/XXXXX)",
            "sensitive": True,
        }
    )
    channel: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Rocket.Chat channel name or ID to send messages to",
        }
    )


class RocketChatProvider(BaseProvider):
    """Send alert messages to Rocket.Chat channels via incoming webhooks."""

    PROVIDER_DISPLAY_NAME = "Rocket.Chat"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_LINK = "https://rocket.chat/"
    PROVIDER_DESCRIPTION = "Send Keep alerts to Rocket.Chat channels via incoming webhooks"
    IS_TESTABLE = True

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RocketChatProviderAuthConfig(
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
        """Send notification to Rocket.Chat channel."""
        self.logger.debug("Sending message to Rocket.Chat")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send message: message body is required"
            )

        display_text = message
        if title:
            display_text = f"*{title}*\n\n{message}"

        payload = {
            "text": display_text,
            "channel": self.authentication_config.channel,
        }

        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code not in (200, 201, 204):
                error_msg = response.text
                raise ProviderException(
                    f"{self.__class__.__name__} failed to send Rocket.Chat message: "
                    f"HTTP {response.status_code} - {error_msg[:200]}"
                )

            self.logger.info(f"Message sent to Rocket.Chat channel {self.authentication_config.channel}")
            return True

        except requests.exceptions.ConnectionError as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to connect to Rocket.Chat: {str(e)}"
            )
        except requests.exceptions.Timeout:
            raise ProviderException(
                f"{self.__class__.__name__} connection to Rocket.Chat timed out"
            )
        except requests.exceptions.RequestException as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send Rocket.Chat message: {str(e)}"
            )

    def test(self):
        """Test the Rocket.Chat connection."""
        self.logger.debug("Testing Rocket.Chat connection")

        if not self.authentication_config:
            self.validate_config()

        payload = {
            "text": "KeepHQ test notification - connection successful!",
            "channel": self.authentication_config.channel,
        }

        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code in (200, 201, 204):
                return {
                    "ok": True,
                    "message": "Rocket.Chat connection successful - test message sent",
                }
            else:
                return {
                    "ok": False,
                    "message": f"Rocket.Chat connection test failed: HTTP {response.status_code} - {response.text[:200]}",
                }

        except requests.exceptions.ConnectionError:
            return {
                "ok": False,
                "message": "Cannot connect to Rocket.Chat webhook URL",
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"Rocket.Chat connection test failed: {str(e)}",
            }
