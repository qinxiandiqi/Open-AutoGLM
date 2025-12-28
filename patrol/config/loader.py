"""
配置加载器 - 负责加载 .env 文件和 YAML 配置文件

这个模块实现了智能配置加载功能：
1. 自动查找并加载 .env 文件（当前目录或项目根目录）
2. 解析 YAML 配置文件
3. 支持环境变量引用（${VAR_NAME} 格式）
4. 实现配置优先级：.env > 环境变量 > YAML > 默认值
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def find_env_file() -> Path | None:
    """
    查找 .env 文件

    搜索顺序：
    1. 当前工作目录
    2. 项目根目录（包含 setup.py 或 pyproject.toml 的目录）

    Returns:
        找到的 .env 文件路径，如果未找到则返回 None
    """
    # 1. 检查当前工作目录
    current_dir = Path.cwd()
    env_path = current_dir / ".env"
    if env_path.exists():
        return env_path

    # 2. 查找项目根目录
    root_dir = _find_project_root(current_dir)
    if root_dir:
        env_path = root_dir / ".env"
        if env_path.exists():
            return env_path

    return None


def _find_project_root(start_dir: Path) -> Path | None:
    """
    查找项目根目录

    通过查找标志文件（setup.py, pyproject.toml, .git）来确定项目根目录

    Args:
        start_dir: 开始搜索的目录

    Returns:
        项目根目录路径，如果未找到则返回 None
    """
    current = start_dir

    # 标志文件列表
    markers = ["setup.py", "pyproject.toml", ".git"]

    while current != current.parent:  # 直到根目录
        # 检查是否有任何标志文件
        if any((current / marker).exists() for marker in markers):
            return current

        current = current.parent

    return None


def load_env_file(env_path: Path | None = None) -> None:
    """
    加载 .env 文件

    Args:
        env_path: .env 文件路径。如果为 None，则自动查找
    """
    if env_path is None:
        env_path = find_env_file()

    if env_path and env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        print(f"✅ 已加载环境变量文件: {env_path}")
    else:
        print("ℹ️  未找到 .env 文件，将使用系统环境变量和默认配置")


def expand_env_vars(value: Any) -> Any:
    """
    展开环境变量引用

    支持格式：
    - ${VAR_NAME}
    - ${VAR_NAME:default_value}

    Args:
        value: 输入值（字符串或其他类型）

    Returns:
        展开环境变量后的值
    """
    if not isinstance(value, str):
        return value

    # 匹配 ${VAR_NAME} 或 ${VAR_NAME:default}
    pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'

    def replace_env_var(match):
        var_name = match.group(1)
        default_value = match.group(2) if match.group(2) is not None else ""
        return os.getenv(var_name, default_value)

    return re.sub(pattern, replace_env_var, value)


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    """
    加载并解析 YAML 配置文件

    Args:
        config_path: YAML 配置文件路径

    Returns:
        解析后的配置字典

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: YAML 格式错误
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)

        if yaml_data is None:
            raise ValueError(f"配置文件为空: {config_path}")

        # 展开所有环境变量引用
        yaml_data = _expand_env_vars_recursive(yaml_data)

        return yaml_data

    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"YAML 格式错误 ({config_path}): {e}")


def _expand_env_vars_recursive(data: Any) -> Any:
    """
    递归展开数据结构中的所有环境变量引用

    Args:
        data: 输入数据（字典、列表或其他类型）

    Returns:
        展开环境变量后的数据
    """
    if isinstance(data, dict):
        return {key: _expand_env_vars_recursive(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_expand_env_vars_recursive(item) for item in data]
    else:
        return expand_env_vars(data)


def find_yaml_configs(configs_dir: str | Path | None = None) -> list[Path]:
    """
    查找所有 YAML 配置文件

    Args:
        configs_dir: 配置目录路径。如果为 None，使用默认的 patrol/configs/

    Returns:
        YAML 配置文件路径列表
    """
    if configs_dir is None:
        # 默认配置目录
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent
        configs_dir = project_root / "patrol" / "configs"

    configs_dir = Path(configs_dir)

    if not configs_dir.exists():
        return []

    # 查找所有 .yaml 和 .yml 文件
    yaml_files = list(configs_dir.glob("*.yaml")) + list(configs_dir.glob("*.yml"))

    # 排除 README 和隐藏文件
    yaml_files = [
        f for f in yaml_files
        if not f.name.startswith(".") and f.name.lower() != "readme.md"
    ]

    return sorted(yaml_files)


def list_available_configs() -> None:
    """列出所有可用的 YAML 配置文件"""
    yaml_files = find_yaml_configs()

    if not yaml_files:
        print("未找到 YAML 配置文件")
        return

    print("可用的巡查配置:")
    print("-" * 50)

    for yaml_file in yaml_files:
        try:
            config_data = load_yaml_config(yaml_file)

            name = config_data.get("name", "未命名配置")
            description = config_data.get("description", "无描述")
            tasks = config_data.get("tasks", [])
            enabled_tasks = [t for t in tasks if t.get("enabled", True)]

            print(f"  📋 {yaml_file.stem}")
            print(f"     描述: {description}")
            print(f"     任务数: {len(enabled_tasks)}/{len(tasks)}")
            print(f"     路径: {yaml_file}")
            print()

        except Exception as e:
            print(f"  ⚠️  {yaml_file.stem}")
            print(f"     错误: {e}")
            print()
