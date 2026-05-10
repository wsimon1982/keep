"""
CiscoWebexProvider is a notification provider for Cisco Webex.
API: https://developer.webex.com/docs/api/v1/messages
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
class CiscoWebexProviderAuthConfig:
    """Cisco Webex authentication configuration."""

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Cisco Webex Bot Access Token (Bearer token)",
            "sensitive": True,
        }
    )
    room_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Cisco Webex Room ID (e.g., YJIxqqqBRfwL9k3n8z3k9z3k9z3k9z3k)",
        }
    )


class CiscoWebexProvider(BaseProvider):
    """Send alert messages to Cisco Webex rooms via bot API."""

    PROVIDER_DISPLAY_NAME = "Cisco Webex"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_LINK = "https://webex.com/"
    PROVIDER_DESCRIPTION = "Send Keep alerts to Cisco Webex rooms via bot API"
    IS_TESTABLE = True
    WEBEX_API = "https://webexapis.com/v1/messages"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CiscoWebexProviderAuthConfig(
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
        """Send notification to Cisco Webex room."""
        self.logger.debug("Sending message to Cisco Webex")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send message: message body is required"
            )

        display_message = message
        if title:
            display_message = f"## {title}\n\n{message}"

        url = CiscoWebexProvider.WEBEX_API
        payload = {
            "roomId": self.authentication_config.room_id,
            "text": display_message,
            "markdown": display_message,
        }

        headers = {
            "Authorization": f"Bearer {self.authentication_config.access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code not in (200, 201):
                error_msg = response.text
                raise ProviderException(
                    f"{self.__class__.__name__} failed to send Webex message: "
                    f"HTTP {response.status_code} - {error_msg[:200]}"
                )

            self.logger.info(f"Message sent to Webex room {self.authentication_config.room_id}")
            return True

        except requests.exceptions.ConnectionError as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to connect to Webex: {str(e)}"
            )
        except requests.exceptions.Timeout:
            raise ProviderException(
                f"{self.__class__.__name__} connection to Webex timed out"
            )
        except requests.exceptions.RequestException as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send Webex message: {str(e)}"
            )

    def test(self):
        """Test the Cisco Webex connection."""
        self.logger.debug("Testing Cisco Webex connection")

        if not self.authentication_config:
            self.validate_config()

        url = CiscoWebexProvider.WEBEX_API
        payload = {
            "roomId": self.authentication_config.room_id,
            "text": "KeepHQ test notification - connection successful!",
        }

        headers = {
            "Authorization": f"Bearer {self.authentication_config.access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code in (200, 201):
                return {
                    "ok": True,
                    "message": "Webex connection successful - test message sent",
                }
            elif response.status_code == 401:
                return {
                    "ok": False,
                    "message": "Webex connection test failed: Invalid token (401 Unauthorized)",
                }
            elif response.status_code == 404:
                return {
                    "ok": False,
                    "message": "Webex connection test failed: Room not found",
                }
            else:
                return {
                    "ok": False,
                    "message": f"Webex connection test failed: HTTP {response.status_code} - {response.text[:200]}",
                }

        except requests.exceptions.ConnectionError:
            return {
                "ok": False,
                "message": f"Cannot connect to Webex API",
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"Webex connection test failed: {str(e)}",
            }
