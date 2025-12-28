"""
配置转换器 - 将 YAML 数据转换为 Python dataclass 对象

这个模块实现了从 YAML 配置到 Python dataclass 的转换：
- yaml_to_patrol_config(): YAML → PatrolConfig
- yaml_to_model_config(): YAML → ModelConfig (YAML 优先，环境变量降级)
- yaml_to_task_config(): YAML → TaskConfig
"""

import os
from typing import Any

from phone_agent.model import ModelConfig

from patrol.models import (
    PatrolConfig,
    TaskConfig,
    ValidationRule,
    ValidationType,
    AutoPatrolConfig,
    ExplorationStrategy,
    ScheduledPatrolConfig,
    NotificationConfig,
    LarkNotificationConfig,
)


def yaml_to_patrol_config(yaml_data: dict[str, Any]) -> PatrolConfig:
    """
    将 YAML 数据转换为 PatrolConfig

    Args:
        yaml_data: 解析后的 YAML 数据

    Returns:
        PatrolConfig 对象

    Raises:
        ValueError: 如果缺少必需字段
    """
    # 验证必需字段
    required_fields = ["name", "description"]
    for field in required_fields:
        if field not in yaml_data:
            raise ValueError(f"缺少必需字段: {field}")

    # 转换 auto_patrol 配置
    auto_patrol_config = yaml_to_auto_patrol_config(yaml_data)

    # 转换 scheduled_patrol 配置
    scheduled_patrol_config = yaml_to_scheduled_patrol_config(yaml_data)

    # 转换通知配置
    notifications_config = yaml_to_notification_config(yaml_data)

    # 转换执行配置
    execution = yaml_data.get("execution", {})
    output = yaml_data.get("output", {})

    # 转换任务列表
    tasks = []
    for task_yaml in yaml_data.get("tasks", []):
        task = yaml_to_task_config(task_yaml)
        tasks.append(task)

    # 如果启用了 auto_patrol，生成探索任务并插入到任务列表开头
    if auto_patrol_config.enabled:
        exploration_task = _generate_exploration_task(auto_patrol_config)
        tasks.insert(0, exploration_task)

    # 创建 PatrolConfig
    config = PatrolConfig(
        name=yaml_data["name"],
        description=yaml_data["description"],
        tasks=tasks,
        auto_patrol=auto_patrol_config,
        scheduled_patrol=scheduled_patrol_config,  # 新增
        # 执行配置
        device_id=execution.get("device_id"),
        lang=execution.get("lang", "cn"),
        continue_on_error=execution.get("continue_on_error", False),
        close_app_after_patrol=execution.get("close_app_after_patrol", True),
        # 输出配置
        save_screenshots=output.get("save_screenshots", True),
        screenshot_dir=output.get("screenshot_dir", "patrol_screenshots"),
        report_dir=output.get("report_dir", "patrol_reports"),
        verbose=output.get("verbose", True),
        # 通知配置
        notifications=notifications_config,  # 新增
    )

    return config


def yaml_to_model_config(yaml_data: dict[str, Any]) -> ModelConfig:
    """
    将 YAML 数据转换为 ModelConfig

    配置优先级：YAML > .env > 系统环境变量 > 默认值

    Args:
        yaml_data: 解析后的 YAML 数据

    Returns:
        ModelConfig 对象
    """
    # 获取模型配置部分（如果存在）
    model_yaml = yaml_data.get("model", {})

    # 读取配置（优先级：YAML > 环境变量 > 默认值）
    base_url = _get_config_with_fallback(
        yaml_value=model_yaml.get("base_url"),
        env_key="PHONE_AGENT_BASE_URL",
        default_value="http://localhost:8000/v1"
    )

    model_name = _get_config_with_fallback(
        yaml_value=model_yaml.get("model_name"),
        env_key="PHONE_AGENT_MODEL",
        default_value="autoglm-phone-9b"
    )

    # API Key 优先级：YAML > ZHIPU_API_KEY > PHONE_AGENT_API_KEY > EMPTY
    api_key = _get_config_with_fallback(
        yaml_value=model_yaml.get("api_key"),
        env_key=["ZHIPU_API_KEY", "PHONE_AGENT_API_KEY"],
        default_value="EMPTY"
    )

    # 创建 ModelConfig
    config = ModelConfig(
        base_url=base_url,
        model_name=model_name,
        api_key=api_key,
    )

    return config


def _get_config_with_fallback(
    yaml_value: Any | None,
    env_key: str | list[str] | None = None,
    default_value: str = ""
) -> str:
    """
    获取配置值（YAML > 环境变量 > 默认值）

    Args:
        yaml_value: YAML 中指定的值（优先级最高）
        env_key: 环境变量名，可以是字符串或列表
        default_value: 默认值

    Returns:
        配置值
    """
    # 1. 如果 YAML 中明确指定了值（且不是 None），直接使用
    if yaml_value is not None:
        return str(yaml_value)

    # 2. 尝试从环境变量读取
    if env_key:
        env_keys = env_key if isinstance(env_key, list) else [env_key]
        for key in env_keys:
            env_value = os.getenv(key)
            if env_value:
                return env_value

    # 3. 使用默认值
    return default_value


def yaml_to_task_config(task_yaml: dict[str, Any]) -> TaskConfig:
    """
    将 YAML 数据转换为 TaskConfig

    Args:
        task_yaml: 解析后的 YAML 任务数据

    Returns:
        TaskConfig 对象

    Raises:
        ValueError: 如果缺少必需字段
    """
    # 验证必需字段
    required_fields = ["name", "task"]
    for field in required_fields:
        if field not in task_yaml:
            raise ValueError(f"任务缺少必需字段 '{field}'")

    # 转换附加验证规则
    additional_validations = []
    for val_yaml in task_yaml.get("additional_validations", []):
        validation = yaml_to_validation_rule(val_yaml)
        additional_validations.append(validation)

    # 创建 TaskConfig
    task = TaskConfig(
        name=task_yaml["name"],
        description=task_yaml.get("description", ""),
        task=task_yaml["task"],
        success_criteria=task_yaml.get("success_criteria", ""),
        # 附加验证
        additional_validations=additional_validations,
        # 快速检查
        expected_keywords=task_yaml.get("expected_keywords"),
        expected_app=task_yaml.get("expected_app"),
        # 任务配置
        enabled=task_yaml.get("enabled", True),
        timeout=task_yaml.get("timeout", 30),
    )

    return task


def yaml_to_validation_rule(val_yaml: dict[str, Any]) -> ValidationRule:
    """
    将 YAML 数据转换为 ValidationRule

    Args:
        val_yaml: 解析后的 YAML 验证规则数据

    Returns:
        ValidationRule 对象

    Raises:
        ValueError: 如果验证类型不支持或缺少必需参数
    """
    # 获取验证类型
    type_str = val_yaml.get("type", "custom")
    try:
        validation_type = ValidationType(type_str)
    except ValueError:
        raise ValueError(f"不支持的验证类型: {type_str}")

    # 创建 ValidationRule
    rule = ValidationRule(
        name=val_yaml.get("name", "未命名验证"),
        validation_type=validation_type,
        # APP_OPENED 参数
        expected_app=val_yaml.get("expected_app"),
        # TEXT_CONTAINS 参数
        keywords=val_yaml.get("keywords"),
        must_contain_all=val_yaml.get("must_contain_all", False),
        # CUSTOM 参数
        custom_validator=val_yaml.get("custom_validator"),  # YAML 中不支持函数，这个字段会留空
        # 通用参数
        error_message=val_yaml.get("error_message", "验证失败"),
    )

    return rule


def yaml_to_auto_patrol_config(yaml_data: dict[str, Any]) -> AutoPatrolConfig:
    """
    将 YAML 数据转换为 AutoPatrolConfig

    Args:
        yaml_data: 解析后的 YAML 数据

    Returns:
        AutoPatrolConfig 对象

    Raises:
        ValueError: 如果探索策略不支持
    """
    auto_patrol_yaml = yaml_data.get("auto_patrol", {})

    # 如果未启用，返回默认禁用配置
    if not auto_patrol_yaml.get("enabled", False):
        return AutoPatrolConfig(enabled=False)

    # 解析探索策略
    strategy_str = auto_patrol_yaml.get("explore_strategy", "breadth_first")
    try:
        explore_strategy = ExplorationStrategy(strategy_str)
    except ValueError:
        raise ValueError(f"不支持的探索策略: {strategy_str}")

    return AutoPatrolConfig(
        enabled=auto_patrol_yaml.get("enabled", True),
        target_app=auto_patrol_yaml.get("target_app"),
        max_pages=auto_patrol_yaml.get("max_pages", 20),
        max_depth=auto_patrol_yaml.get("max_depth", 3),
        max_time=auto_patrol_yaml.get("max_time", 300),
        forbidden_actions=auto_patrol_yaml.get("forbidden_actions", [
            "删除", "支付", "购买", "卸载", "清空", "退出登录"
        ]),
        test_actions=auto_patrol_yaml.get("test_actions", [
            "向下滚动查看内容",
            "向上滚动返回顶部",
        ]),
        explore_strategy=explore_strategy,
        save_discovered_pages=auto_patrol_yaml.get("save_discovered_pages", True),
        screenshot_each_page=auto_patrol_yaml.get("screenshot_each_page", False),
    )


def _generate_exploration_task(auto_patrol_config: AutoPatrolConfig) -> TaskConfig:
    """
    从 AutoPatrolConfig 生成探索任务

    关键:生成一个包含详细探索指令的自然语言任务

    Args:
        auto_patrol_config: 自动巡查配置

    Returns:
        TaskConfig 用于探索任务
    """
    strategy_text = {
        ExplorationStrategy.BREADTH_FIRST: "广度优先（先探索所有一级页面，再深入二级页面）",
        ExplorationStrategy.DEPTH_FIRST: "深度优先（完整探索一个分支后再探索下一个）"
    }

    task_instruction = f"""请自主探索{auto_patrol_config.target_app}应用，执行以下任务：

1. 探索目标：发现应用的主要页面和功能入口（最多探索{auto_patrol_config.max_pages}个页面）
2. 探索深度：最多进入{auto_patrol_config.max_depth}级子页面
3. 安全约束：严禁执行以下操作：{', '.join(auto_patrol_config.forbidden_actions)}
4. 测试要求：在每个发现的页面测试以下功能：
{chr(10).join(f'   - {action}' for action in auto_patrol_config.test_actions)}
5. 探索策略：采用{strategy_text[auto_patrol_config.explore_strategy]}策略
6. 时间限制：{auto_patrol_config.max_time}秒内完成探索

请开始探索，并在每完成一个页面的测试后简要报告进度。"""

    success_criteria = f"""探索完成的标准：
- 发现了应用的主要一级页面（底部导航、侧边栏、主要入口）
- 对每个发现的页面执行了核心功能测试
- 没有执行任何禁止的操作
- 在时间和页面数量限制内完成了探索

请总结探索结果，包括：
1. 发现的页面数量和名称
2. 每个页面的测试结果（通过/失败）
3. 发现的问题（如果有）"""

    return TaskConfig(
        name="自动探索应用",
        description=f"自主探索{auto_patrol_config.target_app}的所有页面并测试核心功能",
        task=task_instruction,
        success_criteria=success_criteria,
        timeout=auto_patrol_config.max_time,
        enabled=True,
    )


def yaml_to_scheduled_patrol_config(yaml_data: dict[str, Any]) -> ScheduledPatrolConfig:
    """
    将 YAML 数据转换为 ScheduledPatrolConfig

    Args:
        yaml_data: 解析后的 YAML 数据

    Returns:
        ScheduledPatrolConfig 对象
    """
    scheduled_patrol_yaml = yaml_data.get("scheduled_patrol", {})

    # 如果未启用，返回默认禁用配置
    if not scheduled_patrol_yaml.get("enabled", False):
        return ScheduledPatrolConfig(enabled=False)

    return ScheduledPatrolConfig(
        enabled=scheduled_patrol_yaml.get("enabled", True),
        success_interval=scheduled_patrol_yaml.get("success_interval", 300),
        failure_interval=scheduled_patrol_yaml.get("failure_interval", 300),
        max_runs=scheduled_patrol_yaml.get("max_runs"),
    )


def yaml_to_notification_config(yaml_data: dict[str, Any]) -> NotificationConfig:
    """
    将 YAML 数据转换为 NotificationConfig

    Args:
        yaml_data: 解析后的 YAML 数据

    Returns:
        NotificationConfig 对象
    """
    notifications_yaml = yaml_data.get("notifications", {})

    # 转换飞书通知配置
    lark_yaml = notifications_yaml.get("lark", {})
    lark_config = LarkNotificationConfig(
        enabled=lark_yaml.get("enabled", False),
        webhook_url=lark_yaml.get("webhook_url"),
        mention_users=lark_yaml.get("mention_users", []),
    )

    # 创建通知配置
    return NotificationConfig(
        lark=lark_config,
        # 未来可以在这里添加其他通知方式
        # dingtalk=yaml_to_dingtalk_config(notifications_yaml),
        # wechat=yaml_to_wechat_config(notifications_yaml),
    )
