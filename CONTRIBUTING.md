# Contributing

感谢你改进 Scientific Experiment Hub。提交 Issue 或 Pull Request 前，请先阅读以下规则。

## 研究数据与隐私

- 不要提交真实实验原始文件、实验数据库、报告、Dashboard、截图或实验室内部路径。
- 不要在 Issue、PR、提交记录或 Actions 日志中粘贴邮箱、令牌、授权码、API Key 或其他凭据。
- 复现问题时只使用最小化的合成数据；必须确保其中不含可识别的研究对象、人员或机构信息。
- 不得通过修复改变“原始数据不可修改、缺失信息不得猜测、冲突不得静默覆盖”的核心约束。

## 开发环境

要求 Python 3.9 或更高版本。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r scripts\requirements.txt
```

macOS / Linux 请使用 `python3 -m venv .venv` 并激活 `.venv/bin/activate`。

## 修改范围

优先保持变更小而明确：

1. Excel 整理变更必须保留原值与来源追溯。
2. 数据库字段变更必须同步检查 schema、模板、导入和报告代码。
3. Dashboard 不得显示或内嵌 QA/QC 评价、缺失值或异常值判断。
4. 统计变更必须继续区分 biological 与 technical replicates。
5. 新依赖必须说明必要性，并更新 `scripts/requirements.txt`。

## 提交前检查

```powershell
python -m compileall -q scripts
python scripts\hub.py --help
python scripts\hub.py create-templates --output "$env:TEMP\seh-templates"
python scripts\hub.py init --project "$env:TEMP\seh-data-center"
```

还应检查：

- `SKILL.md` 的 YAML frontmatter 仍只有 `name` 和 `description`。
- 没有新增真实实验数据、缓存、临时输出或凭据。
- README、引用路径和命令示例与实际 CLI 一致。
- 变更不会覆盖既有原始归档或未解决的数据冲突。

## Issue 与 Pull Request

- Bug 请说明最小复现步骤、预期结果、实际结果、Python 版本和操作系统。
- 功能建议请描述科研工作流中的实际问题，而不只是建议某个技术实现。
- PR 应聚焦一个问题，并说明验证方式和风险边界。
- 涉及 Excel 输出时，说明是否检查过公式、工作表结构和视觉可读性。
- 提交即表示你同意所贡献内容按本仓库的 MIT License 发布。
