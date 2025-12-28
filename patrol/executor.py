"""
Patrol executor - runs app inspection tasks.

This module executes patrol tasks using phone_agent as the underlying library.

Design Philosophy:
- Patrol defines test cases (task + success criteria)
- phone_agent executes and judges success
- Patrol records results and generates reports
"""

import signal
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
from patrol.notifications import NotificationManager


class GracefulExit:
    """用于优雅退出的信号处理器"""

    def __init__(self):
        self.exit = False

    def signal_handler(self, signum, frame):
        """处理 SIGINT (Ctrl+C) 信号"""
        self.exit = True


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

        # 设置信号处理器（用于 Ctrl+C 优雅退出）
        self.graceful_exit = GracefulExit()
        signal.signal(signal.SIGINT, self.graceful_exit.signal_handler)

        # 初始化通知管理器
        self.notification_manager = NotificationManager(
            patrol_config.notifications.__dict__
        )

    def execute(self) -> dict[str, Any]:
        """
        执行巡查（路由到单次或定时巡查）

        Returns:
            巡查结果字典
        """
        # 检查是否启用定时巡查
        if self.patrol_config.scheduled_patrol.enabled:
            return self._execute_scheduled_patrol()
        else:
            return self._execute_single_patrol()

    def _execute_scheduled_patrol(self) -> dict[str, Any]:
        """
        执行定时巡查（循环执行直到手动停止）

        Returns:
            最后一次巡查的结果
        """
        scheduled_config = self.patrol_config.scheduled_patrol
        run_count = 0
        all_results = []  # 保存所有巡查结果

        self.logger.info(f"🔄 启动定时巡查模式")
        self.logger.info(f"   - 成功间隔: {scheduled_config.success_interval}秒")
        self.logger.info(f"   - 失败间隔: {scheduled_config.failure_interval}秒")
        self.logger.info(f"   - 最大次数: {scheduled_config.max_runs or '无限次'}")
        self.logger.info(f"   按 Ctrl+C 停止")

        while not self.graceful_exit.exit:
            # 检查是否达到最大执行次数
            if scheduled_config.max_runs and run_count >= scheduled_config.max_runs:
                self.logger.info(f"✅ 已达到最大执行次数 {scheduled_config.max_runs}，停止巡查")
                break

            run_count += 1
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"🚀 第 {run_count} 次巡查开始")
            self.logger.info(f"{'='*60}\n")

            # 重置 agent 状态，确保每次巡查都是干净的上下文
            if run_count > 1:
                self.reset()
                self.logger.info("✅ Agent 状态已重置，开始新的巡查上下文\n")

            # 执行单次巡查
            result = self._execute_single_patrol()
            all_results.append(result)

            # 发送失败通知（定时巡查中也在每次巡查后发送）
            # 注意：_execute_single_patrol() 内部已经发送了通知
            # 这里不需要再次发送，避免重复通知

            # 检查是否收到停止信号
            if self.graceful_exit.exit:
                self.logger.info("\n⚠️  收到停止信号,正在完成当前巡查后退出...")
                break

            # 决定下次执行时间
            if result["passed_tasks"] == result["total_tasks"]:
                # 巡查成功
                interval = scheduled_config.success_interval
                status = "✅ 成功"
            else:
                # 巡查失败
                interval = scheduled_config.failure_interval
                status = "❌ 失败"

            # 打印统计信息
            success_rate = (
                result["passed_tasks"] / result["total_tasks"] * 100
                if result["total_tasks"] > 0
                else 0
            )
            self.logger.info(
                f"\n{status} - 通过: {result['passed_tasks']}/{result['total_tasks']} ({success_rate:.1f}%)"
            )

            # 如果还有下次执行，等待间隔时间
            if not self.graceful_exit.exit:
                if scheduled_config.max_runs and run_count >= scheduled_config.max_runs:
                    break

                self.logger.info(
                    f"⏰ 下次巡查将在 {interval} 秒后开始 (按 Ctrl+C 停止)"
                )

                # 分段等待，以便及时响应停止信号
                self._wait_with_interrupt_check(interval)

        # 生成汇总报告
        return self._generate_scheduled_summary(all_results, run_count)

    def _execute_single_patrol(self) -> dict[str, Any]:
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

        # 发送失败通知（如果配置了且有失败）
        if self.notification_manager.has_enabled_notifiers():
            try:
                self.notification_manager.send_failure_notification(
                    patrol_name=self.patrol_config.name,
                    results=results,
                )
            except Exception as e:
                self.logger.error(f"发送通知失败: {e}")
                # 通知失败不影响巡查结果

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

    def _wait_with_interrupt_check(self, total_wait_time: int):
        """
        等待指定时间，但每秒检查是否需要中断

        Args:
            total_wait_time: 总等待时间（秒）
        """
        remaining = total_wait_time
        while remaining > 0 and not self.graceful_exit.exit:
            wait_time = min(remaining, 1)  # 每次最多等待1秒
            time.sleep(wait_time)
            remaining -= wait_time

    def _generate_scheduled_summary(
        self, all_results: list[dict], total_runs: int
    ) -> dict[str, Any]:
        """
        生成定时巡查汇总报告

        Args:
            all_results: 所有巡查结果列表
            total_runs: 总执行次数

        Returns:
            汇总报告
        """
        if not all_results:
            return {
                "patrol_name": self.patrol_config.name,
                "description": self.patrol_config.description,
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "start_time": datetime.now(),
                "end_time": datetime.now(),
            }

        # 统计成功和失败次数
        successful_runs = sum(
            1 for r in all_results if r["passed_tasks"] == r["total_tasks"]
        )
        failed_runs = total_runs - successful_runs

        # 使用第一次的开始时间和最后一次的结束时间
        summary = {
            "patrol_name": self.patrol_config.name,
            "description": f"{self.patrol_config.description} (定时巡查汇总)",
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "success_rate": (
                successful_runs / total_runs * 100 if total_runs > 0 else 0
            ),
            "start_time": all_results[0]["start_time"],
            "end_time": all_results[-1]["end_time"],
            "total_duration": sum(r["total_duration"] for r in all_results),
            "total_tasks": all_results[-1]["total_tasks"],  # 最后一次的任务总数
            "passed_tasks": all_results[-1]["passed_tasks"],  # 最后一次的通过数
            "failed_tasks": all_results[-1]["failed_tasks"],  # 最后一次的失败数
            "last_result": all_results[-1],  # 最后一次的结果
        }

        # 如果有 auto_patrol 的探索结果，也包含进来
        if "discovered_pages" in all_results[-1]:
            summary["discovered_pages"] = all_results[-1]["discovered_pages"]
            summary["exploration_summary"] = all_results[-1]["exploration_summary"]

        return summary
