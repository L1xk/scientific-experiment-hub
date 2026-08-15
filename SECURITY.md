# Security Policy

## Supported versions

当前只维护默认分支 `main` 的最新版本。旧提交、旧 ZIP 和未明确发布的历史快照不承诺安全更新。

## Report a vulnerability privately

请不要为安全漏洞创建公开 Issue，也不要在公开截图、PR、Actions 日志或讨论中披露利用细节。

优先使用仓库的 [Private vulnerability reporting](https://github.com/L1xk/scientific-experiment-hub/security/advisories/new) 提交报告。若该入口尚未启用，请先通过维护者的 [GitHub 主页](https://github.com/L1xk) 联系维护者，只说明需要私密沟通，不要公开漏洞细节。

报告建议包含：

- 受影响的 commit 或版本；
- 最小化、无敏感数据的复现步骤；
- 潜在影响和攻击前提；
- 已尝试的缓解措施；
- 可安全公开的合成输入。

不要发送真实实验文件、实验数据库、人员信息、内部路径、账号凭据、API Key、令牌或未脱敏日志。

## Security-relevant examples

以下问题通常应私密报告：

- 原始数据可能被覆盖、删除或错误改写；
- 路径穿越或输出写入项目范围之外；
- 恶意工作簿触发宏、公式、外部链接或命令执行；
- Dashboard、报告或日志意外泄露未请求的实验数据；
- HTML/Excel 内容导致脚本或公式注入；
- 凭据或个人信息被写入仓库、日志或输出。

普通排版问题、文档错误和不涉及敏感数据的功能缺陷可以使用公开 Bug Report。

本项目由个人维护，无法承诺固定响应时限；维护者会在合理可行的范围内确认、评估并协调披露。
