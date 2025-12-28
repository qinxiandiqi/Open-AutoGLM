# Patrol - 应用巡查系统

Patrol 是 Open-AutoGLM 的应用巡查系统，通过配置驱动的方式自动化测试手机应用的核心功能。

## 目录

- [快速开始](#快速开始)
- [核心概念](#核心概念)
- [配置方式](#配置方式)
- [配置文件格式](#配置文件格式)
- [使用示例](#使用示例)
- [配置优先级](#配置优先级)
- [最佳实践](#最佳实践)
- [架构说明](#架构说明)

## 快速开始

### 1. 查看可用配置

```bash
patrol --list-examples
```

### 2. 执行巡查

```bash
# 使用项目提供的配置
patrol --config patrol/configs/wechat_patrol.yaml
patrol --config patrol/configs/jinritoutiao_patrol.yaml

# 使用自定义配置
patrol --config /path/to/my_patrol.yaml
```

### 3. 配置环境变量（推荐）

创建 `.env` 文件：

```bash
# .env
ZHIPU_API_KEY=your_api_key_here
```

## 核心概念

### Patrol 是什么？

Patrol 是一个**配置驱动的应用巡查框架**，用于：
- ✅ 验证手机应用的核心功能是否正常
- ✅ 自动化回归测试
- ✅ CI/CD 集成测试
- ✅ 应用健康检查

### 工作原理

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│ YAML 配置   │ ───> │ Patrol CLI   │ ───> │ Phone Agent │
│ 巡查任务    │      │ 加载并执行    │      │ 执行任务    │
└─────────────┘      └──────────────┘      └─────────────┘
                                                   │
                                                   ▼
                                          ┌─────────────┐
                                          │ 巡查报告    │
                                          │ JSON + MD   │
                                          └─────────────┘
```

**设计理念**：
- **配置即代码**：巡查任务定义在 YAML 文件中，可版本控制
- **Tell, Don't Ask**：告诉 phone_agent 做什么和如何判断成功，由它自主执行
- **清晰分层**：Patrol（应用层）依赖 phone_agent（底层库）

## 配置方式

Patrol 使用 **YAML 配置文件** 定义巡查任务，完全移除了旧的 Python 配置方式。

### 配置文件位置

```
Open-AutoGLM/
├── patrol/
│   └── configs/              # YAML 配置目录
│       ├── wechat_patrol.yaml
│       ├── jinritoutiao_patrol.yaml
│       └── README.md
```

### 环境变量配置

Patrol 会自动加载 `.env` 文件（查找顺序：当前目录 → 项目根目录）

```bash
# .env
ZHIPU_API_KEY=your_api_key
PHONE_AGENT_BASE_URL=http://localhost:8000/v1
PHONE_AGENT_MODEL=autoglm-phone-9b
```

## 配置文件格式

### 完整示例

```yaml
name: "微信基础巡查"
description: "验证微信核心功能是否正常"

# 模型配置（可选）
model:
  base_url: "https://open.bigmodel.cn/api/paas/v4"
  model_name: "autoglm-phone"
  # api_key: "${ZHIPU_API_KEY}"  # 从环境变量读取

# 执行配置
execution:
  device_id: null  # null = 自动检测
  lang: "cn"
  continue_on_error: false
  close_app_after_patrol: true

# 输出配置
output:
  save_screenshots: true
  screenshot_dir: "patrol_screenshots/wechat"
  report_dir: "patrol_reports"
  verbose: true

# 巡查任务
tasks:
  - name: "启动微信"
    description: "验证微信可以正常启动"
    task: "打开微信"
    success_criteria: "微信应用已打开并显示主界面"
    expected_app: "com.tencent.mm"
    enabled: true
    timeout: 30
```

### 配置字段说明

#### 顶层配置

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| name | string | ✅ | 巡查名称 |
| description | string | ✅ | 巡查描述 |
| model | object | ❌ | 模型配置 |
| execution | object | ❌ | 执行配置 |
| output | object | ❌ | 输出配置 |
| tasks | array | ✅ | 任务列表 |

#### model 配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| base_url | string | http://localhost:8000/v1 | 模型 API 地址 |
| model_name | string | autoglm-phone-9b | 模型名称 |
| api_key | string | EMPTY | API Key |

#### execution 配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| device_id | string | null | 设备 ID（null = 自动检测） |
| lang | string | cn | UI 语言（cn/en） |
| continue_on_error | boolean | false | 遇错是否继续 |
| close_app_after_patrol | boolean | true | 巡查结束后是否关闭应用 |

#### output 配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| save_screenshots | boolean | true | 是否保存截图 |
| screenshot_dir | string | patrol_screenshots | 截图保存目录 |
| report_dir | string | patrol_reports | 报告保存目录 |
| verbose | boolean | true | 是否启用详细输出 |

#### task 配置

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| name | string | ✅ | - | 任务名称 |
| description | string | ✅ | - | 任务描述 |
| task | string | ✅ | - | 自然语言任务指令 |
| success_criteria | string | ✅ | - | 成功标准描述 |
| expected_app | string | ❌ | null | 预期应用包名或应用名 |
| expected_keywords | array | ❌ | null | 预期关键词列表 |
| enabled | boolean | ❌ | true | 是否启用任务 |
| timeout | int | ❌ | 30 | 超时时间（秒） |
| additional_validations | array | ❌ | [] | 附加验证规则 |

## 使用示例

### 示例 1：微信巡查

```yaml
# patrol/configs/wechat_patrol.yaml
name: "微信基础巡查"
description: "验证微信核心功能是否正常"

tasks:
  - name: "启动微信"
    task: "打开微信"
    success_criteria: "微信应用已打开并显示主界面"
    expected_app: "com.tencent.mm"

  - name: "查看消息列表"
    task: "等待页面加载完成"
    success_criteria: "消息列表已显示，包含微信或聊天相关内容"
```

```bash
patrol --config patrol/configs/wechat_patrol.yaml
```

### 示例 2：今日头条巡查

```yaml
# patrol/configs/jinritoutiao_patrol.yaml
name: "今日头条首页巡查"
description: "验证今日头条首页的核心功能是否正常"

model:
  base_url: "https://open.bigmodel.cn/api/paas/v4"
  model_name: "autoglm-phone"

tasks:
  - name: "启动今日头条"
    task: "打开今日头条"
    success_criteria: "今日头条应用已打开，显示首页界面"
    expected_app: "com.ss.android.article.news"

  - name: "检查新闻列表"
    task: "等待页面加载完成"
    success_criteria: "首页新闻列表已正常显示"

  - name: "检查视频内容"
    task: "在首页查找并点击一个视频内容"
    success_criteria: "视频内容已打开并可以正常播放"
```

```bash
patrol --config patrol/configs/jinritoutiao_patrol.yaml
```

### 示例 3：使用环境变量

```yaml
# my_patrol.yaml
model:
  api_key: "${ZHIPU_API_KEY}"  # 从环境变量读取
  base_url: "${PHONE_AGENT_BASE_URL:https://open.bigmodel.cn/api/paas/v4}"
```

```bash
# .env
ZHIPU_API_KEY=your_api_key
PHONE_AGENT_BASE_URL=http://localhost:8000/v1

# 执行
patrol --config my_patrol.yaml
```

## 配置优先级

Patrol 使用四级配置优先级系统：

```
1. YAML 配置文件（最高优先级）
   └─> 明确在 YAML 中指定的配置

2. .env 文件
   └─> 当前目录或项目根目录的 .env 文件

3. 系统环境变量
   └─> 操作系统环境变量

4. 代码默认值（最低优先级）
   └─> Python 代码中定义的默认值
```

### 优先级示例

#### 示例 1：YAML 配置优先

```yaml
# config.yaml
model:
  base_url: "https://custom.api.com/v1"
  model_name: "custom-model"
```

```bash
# .env
PHONE_AGENT_BASE_URL=https://env.api.com/v1

# 执行
patrol --config config.yaml

# 结果：使用 YAML 的配置（优先级最高）
# base_url: https://custom.api.com/v1 ✅
# model_name: custom-model ✅
```

#### 示例 2：环境变量降级

```yaml
# config.yaml
model:
  base_url: "https://custom.api.com/v1"
  # model_name 未指定
```

```bash
# .env
PHONE_AGENT_MODEL=env-model

# 执行
patrol --config config.yaml

# 结果：YAML + 环境变量组合
# base_url: https://custom.api.com/v1（来自 YAML）✅
# model_name: env-model（来自 .env）✅
```

### 支持的环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| ZHIPU_API_KEY | 智谱 API Key | 空 |
| PHONE_AGENT_BASE_URL | 模型 API 地址 | http://localhost:8000/v1 |
| PHONE_AGENT_MODEL | 模型名称 | autoglm-phone-9b |
| PHONE_AGENT_API_KEY | 通用 API Key | 空 |
| PHONE_AGENT_DEVICE_ID | 设备 ID | 空 |

## 最佳实践

### 1. 使用描述性命名

```yaml
# ✅ 好的做法
name: "微信支付功能巡查"
description: "验证微信支付流程是否正常工作"

# ❌ 不好的做法
name: "测试1"
description: "测试"
```

### 2. 明确的成功标准

```yaml
# ✅ 好的做法
success_criteria: "支付成功页面已显示，包含支付金额和「支付成功」文字"

# ❌ 不好的做法
success_criteria: "成功"
```

### 3. 合理的超时设置

```yaml
# ✅ 好的做法
- name: "快速操作"
  timeout: 10

- name: "复杂操作"
  timeout: 60

# ❌ 不好的做法
- name: "快速操作"
  timeout: 300  # 太长
```

### 4. 使用环境变量管理敏感信息

```yaml
# ✅ 好的做法
model:
  api_key: "${ZHIPU_API_KEY}"

# ❌ 不好的做法
model:
  api_key: "12345678-1234-1234-1234-123456789abc"  # 硬编码
```

### 5. 组织配置文件

```
patrol/configs/
├── README.md                 # 配置说明
├── wechat_patrol.yaml        # 微信相关
├── jinritoutiao_patrol.yaml  # 今日头条相关
└── my_app_patrol.yaml        # 自定义应用
```

## 架构说明

### 分层架构

```
┌─────────────────────────────────────┐
│        Patrol (应用层)              │
│  - 配置管理 (loader, converter)     │
│  - 任务编排 (executor)              │
│  - 报告生成 (reporter)              │
└─────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│     phone_agent (底层库)            │
│  - 手机操作交互                     │
│  - 任务执行和判断                   │
└─────────────────────────────────────┘
```

### 核心模块

| 模块 | 文件 | 功能 |
|------|------|------|
| CLI | cli.py | 命令行入口 |
| 配置加载 | config/loader.py | .env 和 YAML 加载 |
| 配置转换 | config/converter.py | YAML → Dataclass |
| 执行器 | executor.py | 巡查任务执行 |
| 报告器 | reporter.py | 生成巡查报告 |
| 模型 | models.py | 配置数据模型 |

### 设计原则

1. **YAML 配置优先**：YAML 中明确指定的配置具有最高优先级
2. **环境变量降级**：只在 YAML 未指定时才使用环境变量
3. **配置即代码**：巡查任务定义在 YAML 中，可版本控制和审查
4. **极简 CLI**：只保留 `--config` 和 `--list-examples` 两个参数

## CLI 参数

```bash
patrol --list-examples
```

列出所有可用的 YAML 配置文件。

```bash
patrol --config <yaml_file>
```

使用指定的 YAML 配置文件执行巡查。

**退出码**：
- `0`：所有任务通过
- `1`：至少有一个任务失败
- `130`：用户中断（Ctrl+C）

## 报告格式

Patrol 生成两种格式的报告：

### Markdown 报告

```markdown
# 📱 App 巡查报告

## 巡查信息
- **名称**: 微信基础巡查
- **开始时间**: 2025-12-28 16:00:10
- **总耗时**: 45.23秒

## 📊 总览
| 指标 | 数值 |
|------|------|
| 总任务数 | 2 |
| ✅ 通过 | 2 |
| ❌ 失败 | 0 |
| 成功率 | 100.0% |

## 📋 任务详情
...
```

### JSON 报告

```json
{
  "patrol_name": "微信基础巡查",
  "timestamp": "20251228_160010",
  "results": {
    "total_tasks": 2,
    "passed_tasks": 2,
    "failed_tasks": 0,
    ...
  }
}
```

## 常见问题

### Q: YAML 中指定的配置会被环境变量覆盖吗？

**A**: 不会！配置优先级是：**YAML > .env > 系统环境变量 > 默认值**

只有在 YAML 中未指定某个字段时，才会使用环境变量。

### Q: 如何使用多个 API Key？

**A**: 在不同的 YAML 配置文件中指定不同的 `api_key`：

```yaml
# config1.yaml
model:
  api_key: "key1"

# config2.yaml
model:
  api_key: "key2"
```

### Q: 如何调试配置问题？

**A**: 使用 `--list-examples` 查看配置是否被正确识别：

```bash
patrol --list-examples
```

检查 YAML 语法：
```bash
python -c "import yaml; yaml.safe_load(open('your_config.yaml'))"
```

### Q: 可以在 Python 代码中使用 Patrol 吗？

**A**: 可以！但不推荐使用。推荐直接使用 YAML 配置。如果必须在代码中使用：

```python
from patrol.config.loader import load_env_file, load_yaml_config
from patrol.config.converter import yaml_to_patrol_config, yaml_to_model_config
from patrol import PatrolExecutor, PatrolReporter

# 加载环境变量
load_env_file()

# 加载 YAML 配置
yaml_data = load_yaml_config("path/to/config.yaml")
patrol_config = yaml_to_patrol_config(yaml_data)
model_config = yaml_to_model_config(yaml_data)

# 执行巡查
executor = PatrolExecutor(patrol_config, model_config)
results = executor.execute()
```

## 贡献指南

### 添加新的巡查配置

1. 在 `patrol/configs/` 目录创建新的 YAML 文件
2. 参考现有配置文件的格式
3. 测试配置是否正常工作

### 开发 Patrol

```bash
# 安装开发依赖
pip install -e .

# 运行测试
python -m patrol.cli --list-examples

# 执行巡查
python -m patrol.cli --config patrol/configs/wechat_patrol.yaml
```

## 许可证

与 Open-AutoGLM 项目保持一致。
