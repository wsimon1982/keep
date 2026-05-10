"""
DingTalk provider is an interface for DingTalk messages.
"""

import dataclasses
import json

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class DingTalkProviderAuthConfig:
    """DingTalk authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "DingTalk Webhook Url (Incoming Robot)",
            "sensitive": True,
            "validation": "https_url",
        }
    )
    secret: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "DingTalk Webhook Secret (for HMAC-SHA256 signature)",
            "sensitive": True,
        },
        default="",
    )


class DingTalkProvider(BaseProvider):
    """Send alert message to DingTalk."""

    PROVIDER_DISPLAY_NAME = "DingTalk"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DingTalkProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise Exception("DingTalk webhook URL is required")

    def dispose(self):
        """No need to dispose of anything."""
        pass

    @staticmethod
    def _generate_timestamp_sign(secret: str) -> str:
        """
        Generate timestamp and HMAC-SHA256 signature for DingTalk webhook.
        API docs: https://open.dingtalk.com/document/orgbot/total-control-of-robot-notification
        """
        import hmac
        import hashlib
        import time
        import base64

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        sign = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign_url = base64.urlsafe_b64encode(sign).decode("utf-8")
        return timestamp, sign_url

    def _notify(self, content: str = "", **kwargs: dict):
        """
        Notify alert message to DingTalk using the DingTalk Incoming Webhook API
        API docs: https://open.dingtalk.com/document/robots/custom-robot-access

        Args:
            content (str): The content of the message.
        """
        self.logger.debug("Notifying alert message to DingTalk")
        webhook_url = self.authentication_config.webhook_url

        if not content:
            raise ProviderException(
                f"{self.__class__.__name__}: content is required"
            )

        # Build the message payload
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": "Keep Alert",
                "text": content,
            },
        }

        # If secret is provided, add signature to URL
        if self.authentication_config.secret:
            timestamp, sign = self._generate_timestamp_sign(self.authentication_config.secret)
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            try:
                r = response.json()
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify alert message to DingTalk: {r.get('errcode', 0)} - {r.get('errmsg', response.text)}"
                )
            except Exception:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify alert message to DingTalk: {response.text}"
                )

        # DingTalk returns {"errcode": 0, "errmsg": "ok"} on success
        result = response.json()
        if result.get("errcode", 0) != 0:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify: {result.get('errmsg', 'Unknown error')}"
            )

        self.logger.info("Alert notified to DingTalk")
        return result


if __name__ == "__main__":
    import logging
    import os

    from keep.providers.providers_factory import ProvidersFactory

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    webhook_url = os.environ.get("DINGTALK_WEBHOOK_URL")
    secret = os.environ.get("DINGTALK_SECRET")

    config = {
        "authentication": {"webhook_url": webhook_url, "secret": secret or ""},
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="dingtalk-keephq",
        provider_type="dingtalk",
        provider_config=config,
    )

    provider._notify(content="# [Keep Alert]\n\nTest message from DingTalk provider")
