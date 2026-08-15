# Scientific Experiment Hub

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Codex Skill](https://img.shields.io/badge/Codex-Skill-6f42c1.svg)

一个面向长期科研实验的本地优先 Codex Skill：保存不可变原始文件，把杂乱 Excel 整理成清晰、美观、可追溯的工作簿，并持续维护实验数据库、离线 Dashboard 和阶段报告。

> 最低使用门槛：只提供原始 `.xlsx`、`.xlsm`、`.csv` 或 `.tsv` 数据也可以。日期、实验性质、单位、分组等信息不完整时，系统会明确记录为 `Unknown` / `Not Provided`，不会自行猜测。

## 核心能力

- 原始文件按字节归档并计算 SHA-256，不覆盖、不删除、不静默修改。
- 将布局混乱的 Excel 整理为带边框、筛选、冻结表头、合理列宽和统一数值格式的 `整理版.xlsx`。
- 按“日期 + 实验性质 + Experiment ID”归档多批次实验。
- 增量维护 `Research_Experiment_Database.xlsx` 和实验总索引。
- 区分 biological replicate 与 technical replicate，保留数据来源和版本关系。
- 检测重复导入、数据冲突、缺失元数据和潜在异常值；异常只标记，不自动删除。
- 支持 Experiment Family 分类、跨实验查询、描述性汇总和分析数据交接。
- 生成可双击打开的 self-contained HTML Dashboard；Dashboard 不显示数据质量评价。
- 从当前数据库重新生成 weekly、monthly、stage、semester、project 等报告。
- 可把分析包交给 `nature-statistics`、`nature-figure`、documents、pdf 或 presentations 等 Skill 深化处理。

## 工作流程

```text
原始实验文件
    ↓
不可变归档 + SHA-256
    ↓
美观整理版 Excel
    ↓
实验索引 + 结构化数据库
    ↓
历史查询 / 比较 / 分析交接
    ↓
离线 HTML Dashboard + 阶段报告
```

## 安装

### 安装到 Codex 个人 Skills 目录

Windows PowerShell：

```powershell
git clone https://github.com/L1xk/scientific-experiment-hub.git "$env:USERPROFILE\.codex\skills\scientific-experiment-hub"
Set-Location -LiteralPath "$env:USERPROFILE\.codex\skills\scientific-experiment-hub"
py -3 -m pip install -r scripts\requirements.txt
```

macOS / Linux：

```bash
git clone https://github.com/L1xk/scientific-experiment-hub.git ~/.codex/skills/scientific-experiment-hub
cd ~/.codex/skills/scientific-experiment-hub
python3 -m pip install -r scripts/requirements.txt
```

核心功能只要求 Python 3.9+ 和 `openpyxl>=3.1,<4`。安装或更新后，如 Codex 没有立即发现该 Skill，请重启或刷新 Codex。

## 在 Codex 中使用

可以直接上传实验文件并提出自然语言请求，例如：

```text
使用 scientific-experiment-hub 整理这个实验 Excel。
把今天的实验加入现有数据库。
只整理表格，不进行统计分析。
比较最近五次 T5 实验。
查找以前是否做过 pH 6.5 + 30°C 的条件。
找出目前 L-TA 最高产量对应的实验条件。
更新离线实验 Dashboard。
生成本周科研实验周报。
```

也可以显式调用：

```text
$scientific-experiment-hub 整理并归档这个 Excel，缺失信息不要猜测。
```

## CLI 快速使用

先进入 Skill 目录：

```powershell
Set-Location -LiteralPath "$env:USERPROFILE\.codex\skills\scientific-experiment-hub"
```

查看命令：

```powershell
py -3 scripts\hub.py --help
```

初始化实验数据中心：

```powershell
py -3 scripts\hub.py init --project "D:\codex\实验数据中心"
```

只提供原始数据的快速导入：

```powershell
py -3 scripts\hub.py ingest "D:\实验文件\experiment.xlsx" --project "D:\codex\实验数据中心"
```

提供已知元数据的结构化导入：

```powershell
py -3 scripts\hub.py ingest "D:\实验文件\experiment.xlsx" --project "D:\codex\实验数据中心" --date 2026-08-15 --nature "pH优化实验" --family "LTA-pH-Optimization" --project-id "LTA" --outcome Optimization
```

验证但不导入：

```powershell
py -3 scripts\hub.py validate "D:\实验文件\experiment.xlsx"
```

查询历史、生成 Dashboard 和报告：

```powershell
py -3 scripts\hub.py query --project "D:\codex\实验数据中心" --text "pH 6.5"
py -3 scripts\hub.py dashboard --project "D:\codex\实验数据中心"
py -3 scripts\hub.py report --project "D:\codex\实验数据中心" --type weekly
py -3 scripts\hub.py report --project "D:\codex\实验数据中心" --type monthly --month 2026-08
```

## 典型输出

```text
实验数据中心/
├── 实验文件总索引.xlsx
├── Research_Experiment_Database.xlsx
├── 2026/
│   └── 2026-08/
│       └── 2026-08-15_pH优化实验_EXP-20260815-001/
│           ├── 原始数据/
│           └── 整理结果/
├── 运行记录/
├── 版本快照/
├── 分析交接/
├── Dashboard/
│   └── experiment_dashboard.html
└── 报告/
```

HTML Dashboard 是数据库的离线只读快照，不是数据源。新增实验后应重新生成 Dashboard。

## 数据保护原则

1. 原始文件永远是权威记录，整理和分析只能产生派生文件。
2. 保留 `Raw Value → Cleaned Value → Normalized Value → Analysis Value` 的追溯关系。
3. 缺失信息不猜测；失败、阴性和不确定实验不删除。
4. 同一实验键出现不同值时记录 `DATA CONFLICT`，不静默覆盖。
5. technical replicates 不作为独立 biological `n`。
6. 公开分享仓库时不要提交实验数据中心、原始数据、报告或含实验摘要的 Dashboard。

## 仓库结构

```text
scientific-experiment-hub/
├── SKILL.md                 # Codex 执行规范
├── agents/openai.yaml       # Skill 展示与默认提示
├── assets/templates/        # Excel、Dashboard 和报告模板
├── references/              # 数据模型、统计、可视化和报告规则
└── scripts/                 # 可复用 CLI 与核心实现
```

详细的 Agent 操作规则见 [`SKILL.md`](SKILL.md)。

## 当前边界

- V1 的核心目标是可靠归档和 Excel 初步整理，不替代研究者对实验含义的判断。
- 内置统计以描述性汇总为主；正式推断统计和投稿级科研绘图应交给专业 Skill。
- 旧版 `.xls` 建议先另存为 `.xlsx` 或 CSV，同时保留原文件。
- `.xlsm` 会作为原始文件保存，但不会执行宏。
- PDF、DOCX、PPTX 等最终报告格式由相应文档 Skill 生成。

## License

本项目采用 [MIT License](LICENSE)。
