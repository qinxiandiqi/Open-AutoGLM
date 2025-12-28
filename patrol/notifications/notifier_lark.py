"""
Feishu/Lark notifier implementation.

Sends rich text notifications to Feishu custom bot webhooks.
"""

import json
from typing import Any

import requests

from patrol.notifications.base_notifier import BaseNotifier
from patrol.utils.logger import get_logger


class LarkNotifier(BaseNotifier):
    """
    Feishu/Lark notification bot.

    Uses Feishu custom bot webhook to send rich text messages
    with optional @mentions.
    """

    # Feishu webhook URL format
    WEBHOOK_URL_PREFIX = "https://open.feishu.cn/open-apis/bot/v2/hook/"

    def __init__(self, config: dict[str, Any]):
        """
        Initialize Lark notifier.

        Args:
            config: Configuration dict with keys:
                - enabled: bool, whether notifications are enabled
                - webhook_url: str, Feishu webhook URL
                - mention_users: list[str], optional list of open_ids to @mention
        """
        super().__init__(config)
        self.webhook_url = config.get("webhook_url", "")
        self.mention_users = config.get("mention_users", [])

        # Validate webhook URL
        if self.enabled and not self.webhook_url:
            self.logger.warning("飞书通知已启用，但未配置 webhook_url")
            self.enabled = False

    def send_notification(
        self, patrol_name: str, results: dict[str, Any]
    ) -> bool:
        """
        Send notification to Feishu.

        Args:
            patrol_name: Name of the patrol
            results: Patrol execution results

        Returns:
            True if notification was sent successfully
        """
        if not self._is_enabled():
            self.logger.debug("飞书通知未启用，跳过发送")
            return False

        # Only send notification if there are failures
        if results.get("failed_tasks", 0) == 0:
            self.logger.debug("巡查成功，不发送通知")
            return False

        try:
            # Build rich text message
            message = self._build_rich_text_message(patrol_name, results)

            # Send to Feishu webhook
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            # Check response
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    self.logger.info("飞书通知发送成功")
                    return True
                else:
                    self.logger.error(
                        f"飞书通知发送失败: {data.get('msg', 'Unknown error')}"
                    )
                    return False
            else:
                self.logger.error(
                    f"飞书通知HTTP错误: {response.status_code} - {response.text}"
                )
                return False

        except requests.exceptions.Timeout:
            self.logger.error("飞书通知请求超时")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"飞书通知请求失败: {e}")
            return False
        except Exception as e:
            self.logger.error(f"飞书通知发送异常: {e}")
            return False

    def _build_rich_text_message(
        self, patrol_name: str, results: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Build Feishu rich text message.

        Message structure:
        - Title with alert emoji
        - Patrol information
        - Failed tasks list
        - Optional @mentions

        Args:
            patrol_name: Name of the patrol
            results: Patrol execution results

        Returns:
            Feishu webhook message dict
        """
        # Extract statistics
        total_tasks = results.get("total_tasks", 0)
        passed_tasks = results.get("passed_tasks", 0)
        failed_tasks = results.get("failed_tasks", 0)
        failed_task_list = self._get_failed_tasks(results)

        # Build post content (rich text)
        post_content = {
            "zh_cn": {
                "title": f"🚨 巡查失败: {patrol_name}",
                "content": [
                    # Section 1: Overview
                    [
                        {
                            "tag": "text",
                            "text": f"巡查名称: {patrol_name}\n",
                        },
                        {
                            "tag": "text",
                            "text": f"总任务数: {total_tasks}\n",
                        },
                        {
                            "tag": "text",
                            "text": f"✅ 通过: {passed_tasks}\n",
                        },
                        {
                            "tag": "text",
                            "text": f"❌ 失败: {failed_tasks}\n",
                        },
                    ],
                    # Section 2: Failed tasks
                    *self._build_failed_tasks_section(failed_task_list),
                    # Section 3: @mentions (if configured)
                    *self._build_mentions_section(),
                ]
            }
        }

        # Build complete message
        message = {
            "msg_type": "post",
            "content": {
                "post": post_content
            }
        }

        return message

    def _build_failed_tasks_section(self, failed_tasks: list[dict]) -> list:
        """
        Build content sections for failed tasks.

        Args:
            failed_tasks: List of failed task dictionaries

        Returns:
            List of content sections
        """
        if not failed_tasks:
            return []

        sections = []

        # Header
        sections.append([{"tag": "text", "text": "\n\n失败任务详情:\n"}])

        # Each failed task
        for idx, task in enumerate(failed_tasks, 1):
            task_name = task.get("name", "未知任务")
            task_desc = task.get("description", "")
            task_error = task.get("error", "")
            agent_result = task.get("agent_result", "")

            # Build task section
            task_section = [{"tag": "text", "text": f"\n{idx}. {task_name}\n"}]

            if task_desc:
                task_section.append(
                    {"tag": "text", "text": f"   描述: {task_desc}\n"}
                )

            if task_error:
                task_section.append({"tag": "text", "text": f"   错误: {task_error}\n"})
            elif agent_result:
                # Truncate agent result if too long
                result_preview = agent_result[:200]
                if len(agent_result) > 200:
                    result_preview += "..."
                task_section.append(
                    {"tag": "text", "text": f"   结果: {result_preview}\n"}
                )

            sections.append(task_section)

        return sections

    def _build_mentions_section(self) -> list:
        """
        Build @mentions section if mention_users is configured.

        Returns:
            List of content sections with @mentions
        """
        if not self.mention_users:
            return []

        # Build @mention elements
        mention_elements = [{"tag": "text", "text": "\n\n"}]

        for open_id in self.mention_users:
            mention_elements.append(
                {
                    "tag": "at",
                    "user_id": open_id,
                    "text": f"@{open_id}"
                }
            )

        return [mention_elements]
