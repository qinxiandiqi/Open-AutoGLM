"""
Screenshot management for the patrol system.
"""

import base64
from pathlib import Path
from typing import Optional
from datetime import datetime

from phone_agent.device_factory import get_device_factory


class ScreenshotManager:
    """
    Manages screenshot saving and organization for patrol tasks.

    Screenshots are organized by task name and timestamp.
    """

    def __init__(
        self,
        base_dir: str | Path = "patrol_screenshots",
        save_enabled: bool = True,
    ):
        """
        Initialize screenshot manager.

        Args:
            base_dir: Base directory for saving screenshots
            save_enabled: Whether to save screenshots (can be toggled)
        """
        self.base_dir = Path(base_dir)
        self.save_enabled = save_enabled

        # Create base directory if enabled
        if self.save_enabled:
            self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        task_name: str,
        action: str,
        device_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Capture and save a screenshot for a task action.

        Args:
            task_name: Name of the task
            action: Description of the action
            device_id: Device ID (uses default if None)

        Returns:
            Path to saved screenshot, or None if saving is disabled
        """
        if not self.save_enabled:
            return None

        try:
            # Get device factory and capture screenshot
            factory = get_device_factory()
            screenshot = factory.get_screenshot(device_id)

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Sanitize task name and action for filename
            safe_task = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in task_name)
            safe_action = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in action[:50])

            filename = f"{safe_task}_{timestamp}_{safe_action}.png"
            filepath = self.base_dir / filename

            # Save screenshot
            if screenshot.base64_data:
                image_data = base64.b64decode(screenshot.base64_data)
                filepath.write_bytes(image_data)

                return str(filepath)

        except Exception as e:
            # Log error but don't fail the patrol
            print(f"Warning: Failed to save screenshot: {e}")

        return None

    def get_screenshot_base64(
        self,
        device_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get current screenshot as base64 string.

        Args:
            device_id: Device ID (uses default if None)

        Returns:
            Base64-encoded screenshot, or None if capture failed
        """
        try:
            factory = get_device_factory()
            screenshot = factory.get_screenshot(device_id)
            return screenshot.base64_data
        except Exception:
            return None

    def clear_old_screenshots(
        self,
        days: int = 7,
    ) -> int:
        """
        Clear screenshots older than specified days.

        Args:
            days: Number of days to keep screenshots

        Returns:
            Number of screenshots deleted
        """
        if not self.base_dir.exists():
            return 0

        cutoff_time = datetime.now().timestamp() - (days * 86400)
        deleted_count = 0

        for filepath in self.base_dir.glob("*.png"):
            if filepath.stat().st_mtime < cutoff_time:
                filepath.unlink()
                deleted_count += 1

        return deleted_count
