"""
Patrol - App Inspection System for Open-AutoGLM

This package provides a configuration-driven app inspection framework that uses
phone_agent as the underlying library for device interaction.

Usage:
    from patrol import PatrolExecutor, PatrolReporter
    from patrol.config.examples import wechat_patrol

    patrol_config = wechat_patrol
    executor = PatrolExecutor(patrol_config, model_config)
    results = executor.execute()

    reporter = PatrolReporter(patrol_config)
    report_paths = reporter.generate_reports(results)
"""

from patrol.executor import PatrolExecutor
from patrol.reporter import PatrolReporter
from patrol.models import (
    PatrolConfig,
    TaskConfig,
    ValidationRule,
    ValidationType,
)

__all__ = [
    "PatrolExecutor",
    "PatrolReporter",
    "PatrolConfig",
    "TaskConfig",
    "ValidationRule",
    "ValidationType",
]

__version__ = "0.1.0"
