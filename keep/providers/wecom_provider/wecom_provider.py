"""
WeCom provider is an interface for WeCom (Enterprise WeChat) messages.
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
class WeComProviderAuthConfig:
    """WeCom authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "WeCom Webhook Url (Group Robot)",
            "sensitive": True,
            "validation": "https_url",
        }
    )


class WeComProvider(BaseProvider):
    """Send alert message to WeCom (Enterprise WeChat)."""

    PROVIDER_DISPLAY_NAME = "WeCom"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WeComProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise Exception("WeCom webhook URL is required")

    def dispose(self):
        """No need to dispose of anything."""
        pass

    def _notify(self, content: str = "", **kwargs: dict):
        """
        Notify alert message to WeCom using the WeCom Incoming Webhook API
        API docs: https://developer.work.weixin.qq.com/document/path/91770

        Args:
            content (str): The content of the message.
        """
        self.logger.debug("Notifying alert message to WeCom")
        webhook_url = self.authentication_config.webhook_url

        if not content:
            raise ProviderException(
                f"{self.__class__.__name__}: content is required"
            )

        # WeCom supports markdown messages
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content,
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
                    f"{self.__class__.__name__} failed to notify alert message to WeCom: {r.get('errmsg', response.text)}"
                )
            except Exception:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify alert message to WeCom: {response.text}"
                )

        # WeCom returns {"errcode": 0, "errmsg": "ok"} on success
        result = response.json()
        if result.get("errcode", 0) != 0:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify: {result.get('errmsg', 'Unknown error')}"
            )

        self.logger.info("Alert notified to WeCom")
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

    webhook_url = os.environ.get("WECOM_WEBHOOK_URL")

    config = {
        "authentication": {"webhook_url": webhook_url},
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="wecom-keephq",
        provider_type="wecom",
        provider_config=config,
    )

    provider._notify(content="# [Keep Alert]\n\nTest message from WeCom provider")
