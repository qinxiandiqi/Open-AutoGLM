"""
Configuration models for the patrol system.

This module defines the data structures used to configure patrol tasks.

Design Philosophy:
- Patrol defines test cases (what to test + success criteria)
- phone_agent executes tasks and judges success
- Patrol collects results and generates reports
"""

from dataclasses import dataclass, field
from typing import Any, Callable
from enum import Enum


class ExplorationStrategy(Enum):
    """Exploration strategy for auto patrol."""
    BREADTH_FIRST = "breadth_first"  # Explore all main tabs first
    DEPTH_FIRST = "depth_first"      # Explore each branch completely


class ValidationType(Enum):
    """
    Types of validation strategies for patrol tasks.

    Note: In most cases, you should use success_criteria instead,
    which lets phone_agent judge success intelligently.
    Use ValidationType only for special cases that require custom validation.
    """

    APP_OPENED = "app_opened"  # Verify a specific app is opened
    TEXT_CONTAINS = "text_contains"  # Check if response contains keywords
    CUSTOM = "custom"  # Custom validation function


@dataclass
class ValidationRule:
    """
    Additional validation rule for a patrol task.

    Use this for special cases only. For most scenarios,
    use success_criteria in TaskConfig instead.

    Attributes:
        name: Human-readable name for this validation
        validation_type: Type of validation to perform
        expected_app: Expected app package name (for APP_OPENED)
        keywords: List of keywords to check (for TEXT_CONTAINS)
        must_contain_all: Whether all keywords must match (for TEXT_CONTAINS)
        custom_validator: Custom validation function (for CUSTOM)
        error_message: Error message to display if validation fails
    """

    name: str
    validation_type: ValidationType

    # Parameters for APP_OPENED
    expected_app: str | None = None

    # Parameters for TEXT_CONTAINS
    keywords: list[str] | None = None
    must_contain_all: bool = False

    # Parameters for CUSTOM
    custom_validator: Callable[[], bool] | None = None

    # Common parameters
    error_message: str = "验证失败"

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.validation_type == ValidationType.APP_OPENED and not self.expected_app:
            raise ValueError("expected_app is required for APP_OPENED validation")

        if self.validation_type == ValidationType.TEXT_CONTAINS and not self.keywords:
            raise ValueError("keywords is required for TEXT_CONTAINS validation")

        if self.validation_type == ValidationType.CUSTOM and not self.custom_validator:
            raise ValueError("custom_validator is required for CUSTOM validation")


@dataclass
class DiscoveredPage:
    """
    Represents a page discovered during auto patrol.

    Attributes:
        page_name: Human-readable page name
        page_path: Navigation path to reach this page (e.g., "首页 → 推荐 → 视频")
        depth: Depth level (0 = main page)
        tested: Whether this page was tested
        test_results: Test results for this page
        screenshot_path: Optional screenshot path
    """
    page_name: str
    page_path: str  # e.g., "首页 → 推荐 → 视频"
    depth: int
    tested: bool = False
    test_results: list[dict] = field(default_factory=list)
    screenshot_path: str | None = None


@dataclass
class AutoPatrolConfig:
    """
    Configuration for automatic app exploration and testing.

    Attributes:
        enabled: Whether auto patrol is enabled
        target_app_name: Target app display name (e.g., "今日头条")
        target_app_package: Target app package name (e.g., "com.ss.android.article.news")
        max_pages: Maximum number of pages to explore
        max_depth: Maximum navigation depth (0 = current page only)
        max_time: Maximum exploration time in seconds
        forbidden_actions: List of actions to avoid (safety constraint)
        test_actions: Core functionality tests for each page
        explore_strategy: Exploration strategy (breadth_first/depth_first)
        save_discovered_pages: Whether to save list of discovered pages
        screenshot_each_page: Whether to screenshot each page
    """
    enabled: bool = False
    target_app_name: str | None = None  # 应用显示名称
    target_app_package: str | None = None  # 应用包名

    # Exploration limits
    max_pages: int = 20
    max_depth: int = 3
    max_time: int = 300  # 5 minutes

    # Safety constraints
    forbidden_actions: list[str] = field(default_factory=lambda: [
        "删除", "支付", "购买", "卸载", "清空", "退出登录", "注销"
    ])

    # Testing actions
    test_actions: list[str] = field(default_factory=lambda: [
        "向下滚动查看内容",
        "向上滚动返回顶部",
    ])

    # Strategy
    explore_strategy: ExplorationStrategy = ExplorationStrategy.BREADTH_FIRST

    # Output control
    save_discovered_pages: bool = True
    screenshot_each_page: bool = False


@dataclass
class ScheduledPatrolConfig:
    """
    Configuration for scheduled patrol (continuous monitoring).

    Attributes:
        enabled: Whether scheduled patrol is enabled
        success_interval: Interval after successful patrol (seconds)
        failure_interval: Interval after failed patrol (seconds)
        max_runs: Maximum number of runs (None = unlimited)
    """
    enabled: bool = False
    success_interval: int = 300  # 5 minutes
    failure_interval: int = 300  # 5 minutes
    max_runs: int | None = None  # None = unlimited


@dataclass
class LarkNotificationConfig:
    """
    Configuration for Feishu/Lark notifications.

    Attributes:
        enabled: Whether Feishu notifications are enabled
        webhook_url: Feishu custom bot webhook URL
        mention_users: List of user open_ids to @mention (optional)
    """
    enabled: bool = False
    webhook_url: str | None = None
    mention_users: list[str] = field(default_factory=list)


@dataclass
class NotificationConfig:
    """
    Configuration for all notification channels.

    Attributes:
        lark: Feishu/Lark notification configuration
        # Future: dingtalk: DingTalk notification configuration
        # Future: wechat: WeChat Work notification configuration
    """
    lark: LarkNotificationConfig = field(default_factory=LarkNotificationConfig)


@dataclass
class TaskConfig:
    """
    Configuration for a single patrol task.

    Design: Define the task and success criteria, let phone_agent judge.

    Attributes:
        name: Human-readable task name
        description: Detailed description of what this task checks
        task: Natural language instruction for phone_agent
        success_criteria: Success criteria description (tells phone_agent how to judge)
        additional_validations: Optional additional validation rules (use sparingly!)
        expected_keywords: Optional keywords for quick verification
        expected_app: Optional expected app package name OR app name (supports both formats)
        enabled: Whether this task is enabled
        timeout: Maximum time to wait for task completion (seconds)
    """

    name: str
    description: str
    task: str  # Natural language task instruction
    success_criteria: str  # Success criteria for phone_agent to judge

    # Optional additional validations (use sparingly!)
    additional_validations: list[ValidationRule] = field(default_factory=list)

    # Optional quick checks (supplementary to phone_agent's judgment)
    expected_keywords: list[str] | None = None
    expected_app: str | None = None

    enabled: bool = True
    timeout: int = 30


@dataclass
class PatrolConfig:
    """
    Complete configuration for a patrol run.

    Attributes:
        name: Name of this patrol
        description: Description of what this patrol checks
        tasks: List of tasks to execute
        auto_patrol: Auto patrol configuration
        scheduled_patrol: Scheduled patrol configuration
        device_id: Device ID to use (None for auto-detection)
        lang: Language for UI messages ("cn" or "en")
        continue_on_error: Whether to continue if a task fails
        save_screenshots: Whether to save screenshots during patrol
        screenshot_dir: Directory to save screenshots
        report_dir: Directory to save reports
        verbose: Whether to enable verbose output
        close_app_after_patrol: Whether to close apps after patrol completes
        notifications: Notification configuration
    """

    name: str
    description: str
    tasks: list[TaskConfig]

    # Auto patrol configuration
    auto_patrol: AutoPatrolConfig = field(default_factory=AutoPatrolConfig)

    # Scheduled patrol configuration
    scheduled_patrol: ScheduledPatrolConfig = field(default_factory=ScheduledPatrolConfig)

    # Execution configuration
    device_id: str | None = None
    lang: str = "cn"
    continue_on_error: bool = False

    # Screenshot configuration
    save_screenshots: bool = True
    screenshot_dir: str = "patrol_screenshots"

    # Report configuration
    report_dir: str = "patrol_reports"
    verbose: bool = True

    # Cleanup configuration
    close_app_after_patrol: bool = True

    # Notification configuration
    notifications: NotificationConfig = field(default_factory=NotificationConfig)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.lang not in ("cn", "en"):
            raise ValueError("lang must be either 'cn' or 'en'")

        if not self.tasks and not self.auto_patrol.enabled:
            raise ValueError("At least one task or auto_patrol is required")
