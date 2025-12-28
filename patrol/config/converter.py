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

from patrol.models import PatrolConfig, TaskConfig, ValidationRule, ValidationType


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
    required_fields = ["name", "description", "tasks"]
    for field in required_fields:
        if field not in yaml_data:
            raise ValueError(f"缺少必需字段: {field}")

    # 转换执行配置
    execution = yaml_data.get("execution", {})
    output = yaml_data.get("output", {})

    # 转换任务列表
    tasks = []
    for task_yaml in yaml_data["tasks"]:
        task = yaml_to_task_config(task_yaml)
        tasks.append(task)

    # 创建 PatrolConfig
    config = PatrolConfig(
        name=yaml_data["name"],
        description=yaml_data["description"],
        tasks=tasks,
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
