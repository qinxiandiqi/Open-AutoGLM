#!/usr/bin/env python3
"""
Patrol CLI Tool - App Inspection System Command Line Interface

使用 YAML 配置文件执行巡查任务。

Usage:
    patrol --config patrol/configs/wechat.yaml
    patrol --list-examples
"""

import argparse
import sys
from pathlib import Path


def main():
    """Main CLI entry point."""
    # Import here to avoid circular imports
    from patrol import PatrolExecutor, PatrolReporter
    from patrol.config.loader import load_env_file, list_available_configs, load_yaml_config
    from patrol.config.converter import yaml_to_patrol_config, yaml_to_model_config

    parser = argparse.ArgumentParser(
        prog="patrol",
        description="手机应用巡查系统 - App Inspection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用 YAML 配置文件
  patrol --config patrol/configs/wechat.yaml

  # 列出所有可用配置
  patrol --list-examples

  # 使用自定义配置文件
  patrol --config /path/to/my_patrol.yaml

配置优先级:
  YAML 配置 > .env 文件 > 系统环境变量 > 代码默认值

更多文档: https://github.com/anthropics/open-autoglm
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        help="YAML 配置文件路径",
    )

    parser.add_argument(
        "--list-examples",
        action="store_true",
        help="列出所有可用的 YAML 配置文件",
    )

    args = parser.parse_args()

    # List available configurations
    if args.list_examples:
        list_available_configs()
        return 0

    # Check required parameters
    if not args.config:
        parser.error(
            "--config 是必需参数（使用 --list-examples 查看可用配置）"
        )
        return 1

    # Load environment file (as fallback)
    load_env_file()

    # Load YAML configuration
    config_path = Path(args.config)

    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        return 1

    try:
        yaml_data = load_yaml_config(config_path)
    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}")
        return 1

    # Convert to dataclass objects
    try:
        patrol_config = yaml_to_patrol_config(yaml_data)
        model_config = yaml_to_model_config(yaml_data)
    except Exception as e:
        print(f"❌ 配置转换失败: {e}")
        return 1

    # Execute patrol
    print(f"🚀 开始巡查: {patrol_config.name}")
    print(f"📝 {patrol_config.description}")
    print(f"🤖 模型: {model_config.model_name}")
    print(f"🌐 API: {model_config.base_url}")
    print(f"📱 设备: {patrol_config.device_id or '自动检测'}")
    print(f"🌐 语言: {patrol_config.lang}")
    print(f"🔧 关闭应用: {'是' if patrol_config.close_app_after_patrol else '否'}")
    print("=" * 50)

    try:
        executor = PatrolExecutor(
            patrol_config=patrol_config,
            model_config=model_config,
        )

        results = executor.execute()

        # Generate reports
        reporter = PatrolReporter(patrol_config)
        report_paths = reporter.generate_reports(results)

        # Print results
        print("\n" + "=" * 50)
        print("📊 巡查完成!")
        print(f"总任务数: {results['total_tasks']}")
        print(f"✅ 通过: {results['passed_tasks']}")
        print(f"❌ 失败: {results['failed_tasks']}")

        if results['total_tasks'] > 0:
            success_rate = results['passed_tasks'] / results['total_tasks'] * 100
            print(f"📈 成功率: {success_rate:.1f}%")

        print()
        print("📄 报告:")
        for format_type, path in report_paths.items():
            print(f"  - {format_type.upper()}: {path}")
        print("=" * 50)

        # Return exit code based on success
        return 0 if results['failed_tasks'] == 0 else 1

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        return 130
    except Exception as e:
        print(f"\n\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
