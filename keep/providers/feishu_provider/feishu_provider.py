"""
Feishu provider is an interface for Feishu (Lark) messages.
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
class FeishuProviderAuthConfig:
    """Feishu authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Feishu (Lark) Webhook Url (Custom Bot)",
            "sensitive": True,
            "validation": "https_url",
        }
    )


class FeishuProvider(BaseProvider):
    """Send alert message to Feishu (Lark)."""

    PROVIDER_DISPLAY_NAME = "Feishu"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FeishuProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise Exception("Feishu webhook URL is required")

    def dispose(self):
        """No need to dispose of anything."""
        pass

    def _notify(self, content: str = "", **kwargs: dict):
        """
        Notify alert message to Feishu using the Feishu Incoming Webhook API
        API docs: https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot

        Args:
            content (str): The content of the message.
        """
        self.logger.debug("Notifying alert message to Feishu")
        webhook_url = self.authentication_config.webhook_url

        if not content:
            raise ProviderException(
                f"{self.__class__.__name__}: content is required"
            )

        # Feishu supports interactive cards for rich formatting
        # Using interactive card format for better rendering
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "Keep Alert"},
                    "template": "red",
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content,
                    }
                ],
            },
        }

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            try:
                r = response.json()
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify alert message to Feishu: {r.get('msg', response.text)}"
                )
            except Exception:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify alert message to Feishu: {response.text}"
                )

        # Feishu returns {"code": 0, "msg": "ok"} on success
        result = response.json()
        if result.get("code", 0) != 0:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify: {result.get('msg', 'Unknown error')}"
            )

        self.logger.info("Alert notified to Feishu")
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

    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL")

    config = {
        "authentication": {"webhook_url": webhook_url},
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="feishu-keephq",
        provider_type="feishu",
        provider_config=config,
    )

    provider._notify(content="# [Keep Alert]\n\nTest message from Feishu provider")
