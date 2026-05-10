"""
LineNotifyProvider is a class that implements the BaseProvider interface for LINE Notify messages.
Sends alert messages to LINE Notify group or users via the LINE Notify API.

Note: LINE Notify end of service was March 31, 2025, but API still works.
Migration target: LINE Messaging API (https://developers.line.biz/en/)
"""

import dataclasses
from typing import Any, Optional

import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@dataclasses.dataclass
class LineNotifyProviderAuthConfig:
    """LINE Notify authentication configuration."""

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "LINE Notify Access Token",
            "sensitive": True,
        }
    )


class LineNotifyProvider(BaseProvider):
    """Send alert message to LINE Notify."""

    PROVIDER_DISPLAY_NAME = "LINE Notify"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_LINK = "https://notify-bot.line.me/"
    PROVIDER_DESCRIPTION = "Send notifications to LINE Notify group or users"
    IS_TESTABLE = True

    # LINE Notify API endpoint
    NOTIFY_URL = "https://notify-api.line.me/api/notify"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LineNotifyProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """No resources to dispose."""
        pass

    def _notify(
        self,
        message: str = "",
        image_thumbnail: Optional[str] = None,
        image_file: Optional[str] = None,
        sticker_package_id: Optional[int] = None,
        sticker_id: Optional[int] = None,
        **kwargs: dict[str, Any],
    ):
        """
        Send alert message to LINE Notify.

        Args:
            message (str): The message to send
            image_thumbnail (str): Thumbnail of the image
            image_file (str): Path to image file to send
            sticker_package_id (int): LINE sticker package ID
            sticker_id (int): LINE sticker ID
        """
        access_token = self.authentication_config.access_token

        # Build request headers
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Build request payload
        payload = {"message": message}

        # Add optional parameters
        if image_thumbnail:
            payload["imageThumbnail"] = image_thumbnail
        if sticker_package_id and sticker_id:
            payload["stickerPackageId"] = str(sticker_package_id)
            payload["stickerId"] = str(sticker_id)

        # Send request
        try:
            response = requests.post(
                self.NOTIFY_URL,
                headers=headers,
                data=payload,
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send LINE notification: {e}"
            )

        # Check response
        if not response.ok:
            error_detail = response.text
            try:
                error_detail = response.json().get("message", response.text)
            except Exception:
                pass
            raise ProviderException(
                f"{self.__class__.__name__} failed to send LINE notification: {error_detail}"
            )

        result = response.json()
        self.logger.debug(f"LINE Notify response: {result}")
        return {"status": "ok", "response": result}

    def test(self) -> dict:
        """Test the LINE Notify connection."""
        self.validate_config()
        message = "🔍 LINE Notify Test - Verbindung getestet!"
        try:
            result = self._notify(message=message)
            return {
                "ok": True,
                "message": "LINE Notify Verbindung erfolgreich",
                "result": result,
            }
        except ProviderException as e:
            return {"ok": False, "message": str(e)}


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    import os

    line_access_token = os.environ.get("LINE_NOTIFY_ACCESS_TOKEN")

    if not line_access_token:
        print("LINE_NOTIFY_ACCESS_TOKEN environment variable is required")
        print("Get one from: https://notify-bot.line.me/my/")
        exit(1)

    config = ProviderConfig(
        id="line-notify-test",
        description="LINE Notify Output Provider",
        authentication={"access_token": line_access_token},
    )
    provider = LineNotifyProvider(
        context_manager, provider_id="line-notify-test", config=config
    )
    provider.notify(message="Hello from Keep + LINE Notify!")
    print("✅ Test notification sent to LINE Notify")
