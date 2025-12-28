"""
Base notifier interface.

All notifier implementations should inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import Any

from patrol.utils.logger import get_logger


class BaseNotifier(ABC):
    """
    Base class for all notifiers.

    Each notifier (Lark, DingTalk, WeChat, etc.) should implement
    the send_notification method.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the notifier.

        Args:
            config: Notifier-specific configuration
        """
        self.config = config
        self.logger = get_logger(__name__)
        self.enabled = config.get("enabled", False)

    @abstractmethod
    def send_notification(
        self, patrol_name: str, results: dict[str, Any]
    ) -> bool:
        """
        Send notification.

        Args:
            patrol_name: Name of the patrol
            results: Patrol execution results

        Returns:
            True if notification was sent successfully, False otherwise
        """
        pass

    def _is_enabled(self) -> bool:
        """Check if this notifier is enabled."""
        return self.enabled

    def _get_failed_tasks(self, results: dict[str, Any]) -> list[dict]:
        """Extract failed tasks from results."""
        return [
            task for task in results.get("tasks", []) if not task.get("passed", True)
        ]
