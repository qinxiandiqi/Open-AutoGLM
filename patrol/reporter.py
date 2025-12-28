"""
Patrol report generator.

This module generates inspection reports in multiple formats (Markdown, JSON).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from patrol.models import PatrolConfig
from patrol.utils.logger import get_logger


class PatrolReporter:
    """
    Patrol report generator.

    Generates human-readable reports in Markdown format and machine-readable
    reports in JSON format.
    """

    def __init__(self, patrol_config: PatrolConfig):
        """
        Initialize the reporter.

        Args:
            patrol_config: The patrol configuration
        """
        self.patrol_config = patrol_config
        self.logger = get_logger(__name__)

        # Ensure report directory exists
        Path(patrol_config.report_dir).mkdir(parents=True, exist_ok=True)

    def generate_reports(
        self,
        results: dict[str, Any],
    ) -> dict[str, str]:
        """
        Generate all format reports.

        Args:
            results: Patrol execution results from PatrolExecutor

        Returns:
            Dictionary mapping format names to file paths
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        reports = {}

        # Generate Markdown report
        reports["markdown"] = self._generate_markdown_report(results, timestamp)

        # Generate JSON report
        reports["json"] = self._generate_json_report(results, timestamp)

        return reports

    def _generate_markdown_report(
        self,
        results: dict[str, Any],
        timestamp: str,
    ) -> str:
        """
        Generate Markdown format report.

        Args:
            results: Patrol execution results
            timestamp: Timestamp for filename

        Returns:
            Path to generated report file
        """
        # 检查是否为定时巡查汇总
        if "total_runs" in results and results["total_runs"] > 1:
            return self._generate_scheduled_patrol_report(results, timestamp)

        report_path = (
            Path(self.patrol_config.report_dir) / f"patrol_report_{timestamp}.md"
        )

        # Calculate success rate
        total_tasks = results["total_tasks"]
        passed_tasks = results["passed_tasks"]
        success_rate = (passed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        # Build markdown content
        md_lines = [
            "# 📱 App 巡查报告",
            "",
            "## 巡查信息",
            "",
            f"- **名称**: {self.patrol_config.name}",
            f"- **描述**: {self.patrol_config.description}",
            f"- **开始时间**: {results['start_time'].strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **结束时间**: {results['end_time'].strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **总耗时**: {results['total_duration']:.2f}秒",
            "",
            "## 📊 总览",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 总任务数 | {total_tasks} |",
            f"| ✅ 通过 | {passed_tasks} |",
            f"| ❌ 失败 | {results['failed_tasks']} |",
            f"| 成功率 | {success_rate:.1f}% |",
            "",
            "## 📋 任务详情",
            "",
        ]

        # Add task details
        for task in results["tasks"]:
            status_icon = "✅" if task["passed"] else "❌"
            md_lines.extend(
                [
                    f"### {status_icon} {task['name']}",
                    "",
                    f"**描述**: {task['description']}",
                    f"**状态**: {'通过' if task['passed'] else '失败'}",
                    f"**耗时**: {task['duration']:.2f}秒",
                    "",
                ]
            )

            # Add agent result if available
            if "agent_result" in task and task["agent_result"]:
                md_lines.extend([
                    "#### 执行结果",
                    "",
                    f"``",
                    f"{task['agent_result'][:200]}...",
                    f"```",
                    "",
                ])

            # Add screenshot if available
            if "screenshot" in task:
                md_lines.extend([
                    f"📸 **截图**: {task['screenshot']}",
                    "",
                ])

            # Add additional validation results
            if task.get("additional_validations"):
                md_lines.extend(["", "#### 附加验证结果", ""])
                for val in task["additional_validations"]:
                    val_icon = "✅" if val["passed"] else "❌"
                    md_lines.append(f"- {val_icon} **{val['name']}**: {val.get('message', '')}")

            # Add error if any
            if task.get("error"):
                md_lines.extend(["", "#### ❌ 错误", "", f"```", task["error"], f"```"])

            md_lines.extend(["", "---", ""])

        # NEW: Add exploration summary if auto_patrol was used
        if "exploration_summary" in results:
            md_lines.extend([
                "",
                "## 🔍 自动探索结果",
                "",
                f"- **发现页面数**: {results['exploration_summary']['total_pages_discovered']}",
                f"- **已测试页面**: {results['exploration_summary']['pages_tested']}",
                f"- **探索完成**: {'是' if results['exploration_summary']['exploration_completed'] else '否'}",
                "",
            ])

            # List discovered pages
            if results.get("discovered_pages"):
                md_lines.extend(["### 发现的页面", ""])
                for page in results["discovered_pages"]:
                    status = "✅ 已测试" if page.get("tested") else "⏭️ 未测试"
                    test_result = f" ({page.get('test_result', 'N/A')})" if page.get("tested") else ""
                    md_lines.append(f"- {status} **{page['page_name']}**{test_result}")
                md_lines.extend(["", "---", ""])

        # Write to file
        md_content = "\n".join(md_lines)
        report_path.write_text(md_content, encoding="utf-8")
        self.logger.info(f"Markdown 报告已保存: {report_path}")

        return str(report_path)

    def _generate_scheduled_patrol_report(
        self,
        results: dict[str, Any],
        timestamp: str,
    ) -> str:
        """
        生成定时巡查汇总报告

        Args:
            results: 巡查执行结果
            timestamp: 时间戳

        Returns:
            报告文件路径
        """
        report_path = (
            Path(self.patrol_config.report_dir) / f"patrol_report_{timestamp}.md"
        )

        # Build markdown content
        md_lines = [
            "# 🔄 定时巡查汇总报告",
            "",
            "## 巡查信息",
            "",
            f"- **名称**: {self.patrol_config.name}",
            f"- **描述**: {self.patrol_config.description}",
            f"- **开始时间**: {results['start_time'].strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **结束时间**: {results['end_time'].strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **总运行时长**: {results['total_duration']:.2f}秒",
            "",
            "## 📊 执行统计",
            "",
            f"- **总执行次数**: {results['total_runs']}",
            f"- **✅ 成功次数**: {results['successful_runs']}",
            f"- **❌ 失败次数**: {results['failed_runs']}",
            f"- **成功率**: {results['success_rate']:.1f}%",
            "",
        ]

        # 添加最后一次巡查的详情
        last_result = results.get("last_result")
        if last_result:
            total_tasks = results.get("total_tasks", last_result.get("total_tasks", 0))
            passed_tasks = results.get("passed_tasks", last_result.get("passed_tasks", 0))
            failed_tasks = results.get("failed_tasks", last_result.get("failed_tasks", 0))
            success_rate = (
                (passed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            )

            md_lines.extend([
                "## 📋 最后一次巡查详情",
                "",
                f"- **通过任务**: {passed_tasks}/{total_tasks}",
                f"- **失败任务**: {failed_tasks}",
                f"- **成功率**: {success_rate:.1f}%",
                f"- **耗时**: {last_result['total_duration']:.2f}秒",
                "",
            ])

            # 添加最后一次的任务列表
            if "tasks" in last_result:
                md_lines.extend(["### 任务列表", ""])
                for task in last_result["tasks"]:
                    status_icon = "✅" if task["passed"] else "❌"
                    md_lines.append(f"- {status_icon} **{task['name']}**: {task.get('description', '')}")
                md_lines.extend(["", ""])

        # 添加探索结果（如果有）
        if "exploration_summary" in results:
            md_lines.extend([
                "## 🔍 自动探索结果（最后一次）",
                "",
                f"- **发现页面数**: {results['exploration_summary']['total_pages_discovered']}",
                f"- **已测试页面**: {results['exploration_summary']['pages_tested']}",
                f"- **探索完成**: {'是' if results['exploration_summary']['exploration_completed'] else '否'}",
                "",
            ])

            # List discovered pages
            if results.get("discovered_pages"):
                md_lines.extend(["### 发现的页面", ""])
                for page in results["discovered_pages"]:
                    status = "✅ 已测试" if page.get("tested") else "⏭️ 未测试"
                    test_result = f" ({page.get('test_result', 'N/A')})" if page.get("tested") else ""
                    md_lines.append(f"- {status} **{page['page_name']}**{test_result}")
                md_lines.extend(["", ""])

        # Write to file
        md_content = "\n".join(md_lines)
        report_path.write_text(md_content, encoding="utf-8")
        self.logger.info(f"定时巡查 Markdown 报告已保存: {report_path}")

        return str(report_path)

    def _generate_json_report(
        self,
        results: dict[str, Any],
        timestamp: str,
    ) -> str:
        """
        Generate JSON format report.

        Args:
            results: Patrol execution results
            timestamp: Timestamp for filename

        Returns:
            Path to generated report file
        """
        report_path = (
            Path(self.patrol_config.report_dir) / f"patrol_report_{timestamp}.json"
        )

        # Convert datetime objects to strings
        def json_serializer(obj: Any) -> str:
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        # Build report data
        report_data = {
            "patrol_name": self.patrol_config.name,
            "description": self.patrol_config.description,
            "timestamp": timestamp,
            "results": results,
        }

        # Write to file
        report_path.write_text(
            json.dumps(report_data, ensure_ascii=False, indent=2, default=json_serializer),
            encoding="utf-8",
        )
        self.logger.info(f"JSON 报告已保存: {report_path}")

        return str(report_path)
