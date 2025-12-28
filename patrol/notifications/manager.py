"""
Notification manager for patrol system.

This module manages multiple notification channels and sends failure notifications.
"""

from typing import Any

from patrol.notifications.base_notifier import BaseNotifier
from patrol.notifications.notifier_lark import LarkNotifier
from patrol.utils.logger import get_logger


class NotificationManager:
    """
    Manages all notification channels.

    This class is responsible for:
    - Initializing enabled notifiers
    - Sending failure notifications to all channels
    - Handling errors gracefully
    """

    NOTIFIER_TYPES = {
        "lark": LarkNotifier,
    }

    def __init__(self, notifications_config: dict[str, Any]):
        """
        Initialize the notification manager.

        Args:
            notifications_config: Notification configuration dictionary
        """
        self.config = notifications_config
        self.logger = get_logger(__name__)
        self.notifiers: list[BaseNotifier] = []
        self._initialize_notifiers()

    def _initialize_notifiers(self):
        """
        Initialize all configured notifiers.

        Only initializes notifiers that are enabled in the configuration.
        """
        if not self.config:
            return

        for notifier_type, NotifierClass in self.NOTIFIER_TYPES.items():
            notifier_config = self.config.get(notifier_type, {})
            if notifier_config.get("enabled", False):
                try:
                    notifier = NotifierClass(notifier_config)
                    self.notifiers.append(notifier)
                    self.logger.info(f"已启用 {notifier_type} 通知")
                except Exception as e:
                    self.logger.error(f"初始化 {notifier_type} 通知器失败: {e}")

    def send_failure_notification(
        self, patrol_name: str, results: dict[str, Any]
    ) -> dict[str, bool]:
        """
        Send failure notification to all enabled channels.

        Args:
            patrol_name: Name of the patrol
            results: Patrol execution results

        Returns:
            Dictionary mapping notifier type names to success status
        """
        if not self.notifiers:
            return {}

        if results.get("failed_tasks", 0) == 0:
            return {}

        results_map = {}
        for notifier in self.notifiers:
            notifier_type = notifier.__class__.__name__
            try:
                success = notifier.send_notification(patrol_name, results)
                results_map[notifier_type] = success
            except Exception as e:
                self.logger.error(f"{notifier_type} 发送通知异常: {e}")
                results_map[notifier_type] = False

        return results_map

    def has_enabled_notifiers(self) -> bool:
        """
        Check if there are any enabled notifiers.

        Returns:
            True if at least one notifier is enabled
        """
        return len(self.notifiers) > 0
