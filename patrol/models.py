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
        device_id: Device ID to use (None for auto-detection)
        lang: Language for UI messages ("cn" or "en")
        continue_on_error: Whether to continue if a task fails
        save_screenshots: Whether to save screenshots during patrol
        screenshot_dir: Directory to save screenshots
        report_dir: Directory to save reports
        verbose: Whether to enable verbose output
        close_app_after_patrol: Whether to close apps after patrol completes
    """

    name: str
    description: str
    tasks: list[TaskConfig]

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

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.lang not in ("cn", "en"):
            raise ValueError("lang must be either 'cn' or 'en'")

        if not self.tasks:
            raise ValueError("At least one task is required")
