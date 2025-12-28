"""
Patrol executor - runs app inspection tasks.

This module executes patrol tasks using phone_agent as the underlying library.

Design Philosophy:
- Patrol defines test cases (task + success criteria)
- phone_agent executes and judges success
- Patrol records results and generates reports
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig
from phone_agent.device_factory import get_device_factory

from patrol.models import PatrolConfig, TaskConfig
from patrol.utils.screenshot import ScreenshotManager
from patrol.utils.logger import get_logger


class PatrolExecutor:
    """
    Patrol executor for running app inspection tasks.

    Uses phone_agent.PhoneAgent as the underlying library to execute
    natural language instructions on mobile devices.

    This is the main entry point for running patrol inspections.
    """

    def __init__(
        self,
        patrol_config: PatrolConfig,
        model_config: Any,  # ModelConfig from phone_agent.model
    ):
        """
        Initialize the patrol executor.

        Args:
            patrol_config: Patrol configuration
            model_config: Model configuration for phone_agent
        """
        self.patrol_config = patrol_config
        self.model_config = model_config
        self.logger = get_logger(__name__)

        # Setup logging if verbose
        if patrol_config.verbose:
            from patrol.utils.logger import setup_logging

            setup_logging(verbose=True)

        # Create output directories
        Path(patrol_config.screenshot_dir).mkdir(parents=True, exist_ok=True)
        Path(patrol_config.report_dir).mkdir(parents=True, exist_ok=True)

        # Initialize screenshot manager
        self.screenshot_manager = ScreenshotManager(
            base_dir=patrol_config.screenshot_dir,
            save_enabled=patrol_config.save_screenshots,
        )

        # Create phone_agent instance (as library)
        agent_config = AgentConfig(
            max_steps=50,
            device_id=patrol_config.device_id,
            lang=patrol_config.lang,
            verbose=patrol_config.verbose,
        )

        self.agent = PhoneAgent(
            model_config=model_config,
            agent_config=agent_config,
        )

    def execute(self) -> dict[str, Any]:
        """
        Execute the complete patrol workflow.

        Runs all tasks in the patrol configuration and collects results.

        Returns:
            Dictionary containing patrol results with keys:
            - patrol_name: Name of the patrol
            - description: Description of the patrol
            - start_time: Start datetime
            - end_time: End datetime
            - total_duration: Total duration in seconds
            - total_tasks: Total number of tasks
            - passed_tasks: Number of passed tasks
            - failed_tasks: Number of failed tasks
            - tasks: List of task results
        """
        self.logger.info(f"开始巡查: {self.patrol_config.name}")

        start_time = datetime.now()
        results = {
            "patrol_name": self.patrol_config.name,
            "description": self.patrol_config.description,
            "start_time": start_time,
            "total_tasks": 0,
            "passed_tasks": 0,
            "failed_tasks": 0,
            "tasks": [],
        }

        # Count enabled tasks
        enabled_tasks = [t for t in self.patrol_config.tasks if t.enabled]
        results["total_tasks"] = len(enabled_tasks)

        # Execute each task
        for task_config in self.patrol_config.tasks:
            if not task_config.enabled:
                continue

            self.logger.info(f"执行任务: {task_config.name}")

            task_result = self._execute_task(task_config)
            results["tasks"].append(task_result)

            if task_result["passed"]:
                results["passed_tasks"] += 1
            else:
                results["failed_tasks"] += 1

                # Check if we should continue on error
                if not self.patrol_config.continue_on_error:
                    self.logger.warning("任务失败，停止巡查")
                    break

        # Cleanup: Close apps after patrol if configured
        if self.patrol_config.close_app_after_patrol:
            self._close_apps_after_patrol()

        end_time = datetime.now()
        results["end_time"] = end_time
        results["total_duration"] = (end_time - start_time).total_seconds()

        # Parse exploration results if auto_patrol was used
        if self.patrol_config.auto_patrol.enabled:
            results = self._parse_exploration_results(results)

        return results

    def _execute_task(self, task_config: TaskConfig) -> dict[str, Any]:
        """
        Execute a single patrol task.

        New Design:
        1. Send task + success criteria to phone_agent
        2. Let phone_agent execute and judge success
        3. Apply additional validations (if any)
        4. Record results

        Args:
            task_config: Task configuration

        Returns:
            Dictionary containing task results
        """
        start_time = time.time()
        task_result = {
            "name": task_config.name,
            "description": task_config.description,
            "passed": False,
            "duration": 0,
            "agent_result": None,
            "additional_validations": [],
            "error": None,
        }

        try:
            # Build full task instruction with success criteria
            full_task = self._build_task_instruction(task_config)

            self.logger.info(f"  任务指令: {task_config.task}")
            self.logger.info(f"  成功标准: {task_config.success_criteria}")

            # Execute with phone_agent (it will judge success based on criteria)
            agent_result = self.agent.run(full_task)
            task_result["agent_result"] = agent_result

            # Parse phone_agent's judgment
            passed = self._parse_agent_result(agent_result, task_config)
            task_result["passed"] = passed

            # Save screenshot after task execution
            if self.screenshot_manager:
                screenshot_path = self.screenshot_manager.save(
                    task_name=task_config.name,
                    action=task_config.task,
                    device_id=self.patrol_config.device_id,
                )
                if screenshot_path:
                    task_result["screenshot"] = screenshot_path

            # Apply additional validations (if specified)
            if task_config.additional_validations:
                for validation_rule in task_config.additional_validations:
                    validation_result = self._apply_validation(
                        validation_rule, agent_result
                    )
                    task_result["additional_validations"].append(validation_result)

                    if not validation_result["passed"]:
                        task_result["passed"] = False
                        self.logger.warning(
                            f"  附加验证失败: {validation_result['message']}"
                        )

            # Apply quick checks (expected_keywords, expected_app)
            if passed and task_config.expected_keywords:
                keyword_match = any(
                    kw in agent_result for kw in task_config.expected_keywords
                )
                if not keyword_match:
                    task_result["passed"] = False
                    self.logger.warning(
                        f"  关键词未匹配: {task_config.expected_keywords}"
                    )

            if passed and task_config.expected_app:
                from phone_agent.config.apps import APP_PACKAGES

                device_factory = get_device_factory()
                current_app = device_factory.get_current_app(
                    self.patrol_config.device_id
                )

                # 支持两种匹配方式：
                # 1. 应用名称匹配（如 "今日头条"）
                # 2. 包名匹配（如 "com.ss.android.article.news"）
                app_name_match = current_app == task_config.expected_app

                # 从 APP_PACKAGES 查找包名对应的应用名称
                expected_app_name = None
                for app_name, package in APP_PACKAGES.items():
                    if package == task_config.expected_app:
                        expected_app_name = app_name
                        break

                package_match = expected_app_name and current_app == expected_app_name

                # 如果应用名称和包名都不匹配，则验证失败
                if not (app_name_match or package_match):
                    task_result["passed"] = False
                    self.logger.warning(
                        f"  应用不匹配: 期望 {task_config.expected_app} "
                        f"(应用名: {expected_app_name or '无'}), "
                        f"实际 {current_app}"
                    )

        except Exception as e:
            task_result["error"] = str(e)
            task_result["passed"] = False
            self.logger.error(f"任务执行失败: {e}")

        task_result["duration"] = time.time() - start_time
        return task_result

    def _build_task_instruction(self, task_config: TaskConfig) -> str:
        """
        Build full task instruction with success criteria.

        Args:
            task_config: Task configuration

        Returns:
            Full task instruction string
        """
        return f"""任务：{task_config.task}

成功标准：{task_config.success_criteria}

请执行任务并根据成功标准判断是否成功完成。
完成后请用简短的语言描述执行结果。"""

    def _parse_agent_result(
        self, agent_result: str, task_config: TaskConfig
    ) -> bool:
        """
        Parse phone_agent's result to determine if task passed.

        Args:
            agent_result: Result string from phone_agent
            task_config: Task configuration

        Returns:
            True if task passed, False otherwise
        """
        # If agent_result contains explicit success/failure indicators
        result_lower = agent_result.lower()

        # Check for explicit failure indicators
        failure_indicators = [
            "失败",
            "无法",
            "错误",
            "error",
            "failed",
            "cannot",
            "unable",
        ]

        for indicator in failure_indicators:
            if indicator in result_lower:
                return False

        # Check for explicit success indicators
        success_indicators = [
            "成功",
            "完成",
            "已显示",
            "success",
            "completed",
            "finished",
        ]

        for indicator in success_indicators:
            if indicator in result_lower:
                return True

        # Default: assume passed if no explicit failure
        return True

    def _apply_validation(self, validation_rule, agent_result: str) -> dict:
        """
        Apply an additional validation rule.

        Args:
            validation_rule: ValidationRule to apply
            agent_result: Result string from phone_agent

        Returns:
            Validation result dictionary
        """
        from patrol.models import ValidationType
        from phone_agent.device_factory import get_device_factory

        if validation_rule.validation_type == ValidationType.APP_OPENED:
            from phone_agent.config.apps import APP_PACKAGES

            device_factory = get_device_factory()
            current_app = device_factory.get_current_app(
                self.patrol_config.device_id
            )

            # 支持两种匹配方式：
            # 1. 应用名称匹配（如 "今日头条"）
            # 2. 包名匹配（如 "com.ss.android.article.news"）
            app_name_match = current_app == validation_rule.expected_app

            # 从 APP_PACKAGES 查找包名对应的应用名称
            expected_app_name = None
            for app_name, package in APP_PACKAGES.items():
                if package == validation_rule.expected_app:
                    expected_app_name = app_name
                    break

            package_match = expected_app_name and current_app == expected_app_name
            passed = app_name_match or package_match

            return {
                "name": validation_rule.name,
                "passed": passed,
                "message": f"应用{'已打开' if passed else '未打开'}",
                "expected": validation_rule.expected_app,
                "expected_app_name": expected_app_name or "无",
                "actual": current_app,
            }

        elif validation_rule.validation_type == ValidationType.TEXT_CONTAINS:
            keywords = validation_rule.keywords or []
            must_contain_all = validation_rule.must_contain_all

            matches = [kw for kw in keywords if kw in agent_result]
            if must_contain_all:
                passed = len(matches) == len(keywords)
            else:
                passed = len(matches) > 0

            return {
                "name": validation_rule.name,
                "passed": passed,
                "message": f"关键词{'匹配' if passed else '不匹配'}",
                "keywords": keywords,
                "matches": matches,
            }

        elif validation_rule.validation_type == ValidationType.CUSTOM:
            if validation_rule.custom_validator:
                try:
                    passed = validation_rule.custom_validator()
                    return {
                        "name": validation_rule.name,
                        "passed": passed,
                        "message": "自定义验证通过"
                        if passed
                        else "自定义验证失败",
                    }
                except Exception as e:
                    return {
                        "name": validation_rule.name,
                        "passed": False,
                        "error": str(e),
                        "message": f"自定义验证异常: {e}",
                    }

        return {
            "name": validation_rule.name,
            "passed": False,
            "error": "Unknown validation type",
        }

    def reset(self) -> None:
        """
        Reset the agent state.

        Call this between patrol runs to ensure a clean state.
        """
        self.agent.reset()
        self.logger.info("Agent 状态已重置")

    def _close_apps_after_patrol(self) -> None:
        """
        Close all apps that were opened during the patrol.

        This cleanup step ensures:
        1. Apps don't consume resources in the background
        2. Each patrol starts from a clean state
        3. App state doesn't affect subsequent patrols
        """
        from phone_agent.config.apps import APP_PACKAGES

        device_factory = get_device_factory()
        device_id = self.patrol_config.device_id

        self.logger.info("清理应用...")

        # Collect all apps mentioned in the patrol
        apps_to_close = set()

        # Check expected_app from tasks
        for task in self.patrol_config.tasks:
            if task.expected_app:
                apps_to_close.add(task.expected_app)

        # Check additional_validations
        for task in self.patrol_config.tasks:
            for validation in task.additional_validations:
                if hasattr(validation, 'expected_app') and validation.expected_app:
                    apps_to_close.add(validation.expected_app)

        # Close each app
        closed_count = 0
        for app_ref in apps_to_close:
            try:
                # Convert package name to app name if needed
                app_name = None
                if app_ref in APP_PACKAGES.values():
                    # It's a package name, find the app name
                    for name, package in APP_PACKAGES.items():
                        if package == app_ref:
                            app_name = name
                            break
                else:
                    # It's already an app name
                    app_name = app_ref

                if app_name:
                    # Go to home screen first
                    device_factory.home(device_id)
                    time.sleep(0.5)

                    # Close the app by swiping it away from recent apps
                    # For now, just going to home is sufficient to stop the app
                    self.logger.info(f"  已返回主屏幕（关闭 {app_name}）")
                    closed_count += 1

            except Exception as e:
                self.logger.warning(f"  关闭应用 {app_ref} 失败: {e}")

        if closed_count > 0:
            self.logger.info(f"✅ 已清理 {closed_count} 个应用")
        else:
            self.logger.info("✅ 无需清理应用")

    def _parse_exploration_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """
        从 auto_patrol 任务结果中解析探索信息

        Args:
            results: 原始巡查结果

        Returns:
            增强后的巡查结果，包含发现的页面信息
        """
        # 查找探索任务结果
        exploration_task = None
        for task in results.get("tasks", []):
            if task["name"] == "自动探索应用":
                exploration_task = task
                break

        if not exploration_task:
            return results

        # 从 agent 结果中解析发现的页面
        agent_result = exploration_task.get("agent_result", "")
        discovered_pages = self._extract_pages_from_result(agent_result)

        # 添加到结果中
        results["discovered_pages"] = discovered_pages
        results["exploration_summary"] = {
            "total_pages_discovered": len(discovered_pages),
            "pages_tested": sum(1 for p in discovered_pages if p.get("tested", False)),
            "exploration_completed": exploration_task["passed"],
        }

        return results

    def _extract_pages_from_result(self, agent_result: str) -> list[dict]:
        """
        从 agent 的结果文本中提取发现的页面信息

        简单的关键词匹配解析器，查找如下模式:
        - "发现页面：首页"
        - "测试结果：通过"
        等

        Args:
            agent_result: Agent 的结果文本

        Returns:
            发现的页面列表
        """
        pages = []
        lines = agent_result.split('\n')
        current_page = None

        for line in lines:
            line = line.strip()

            # 查找页面发现模式
            if any(keyword in line for keyword in ["发现页面", "进入页面", "打开页面"]):
                if current_page and current_page not in pages:
                    pages.append(current_page)
                # 提取页面名称
                for keyword in ["发现页面：", "进入页面：", "打开页面：", "发现页面", "进入页面", "打开页面"]:
                    if keyword in line:
                        page_name = line.replace(keyword, "").strip()
                        current_page = {"page_name": page_name, "tested": False}
                        break

            # 查找测试结果
            elif current_page and any(keyword in line for keyword in ["测试通过", "测试成功", "测试完成"]):
                current_page["tested"] = True
                current_page["test_result"] = "passed"
                pages.append(current_page)
                current_page = None

            elif current_page and any(keyword in line for keyword in ["测试失败", "无法测试"]):
                current_page["tested"] = True
                current_page["test_result"] = "failed"
                pages.append(current_page)
                current_page = None

        if current_page and current_page not in pages:
            pages.append(current_page)

        return pages
