# agent-env-doctor

**Pre-alpha**：面向终端 Agent 的 Terminal-Bench 环境预检与失败归因工具。

[English](README.md) | [Terminal-Bench](https://github.com/harbor-framework/terminal-bench) | [Harbor Framework](https://harborframework.com/)

`agent-env-doctor` 是一个本地开发者工具，用于回答仅凭 benchmark 分数无法回答的问题：

> 是 Agent 没有完成任务，还是任务环境先让 Agent 无法运行？

它计划在评测前检查 Terminal-Bench 任务环境，在运行后分析产物，并生成带证据的 Markdown 或 JSON 报告。目标是让终端 Agent 的评测可复现，且每次失败都能被合理归因。

## 项目状态

本仓库处于 **pre-alpha** 阶段，已提供可从源码运行的本地 Python CLI，供早期验证和反馈使用。现有检查项和产物解析器只覆盖规划 MVP 的一部分，并且在 `0.1.0` 前仍可能调整。请勿仅凭 pre-alpha 的结论发布 benchmark 结果。

项目采用 [Apache-2.0](LICENSE) 许可证。

### 从源码运行

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"

# 在 Terminal-Bench 检出目录中执行，或传入任务的绝对路径。
.venv/bin/agent-env-doctor check hello-world
.venv/bin/agent-env-doctor analyze /path/to/agent-run --format json
```

当前 `check` 会验证任务结构、Dockerfile/测试资源是否存在，以及 Docker CLI 和 daemon 是否可用；`analyze` 会识别 JUnit XML、JSON 状态字段和部分基础设施/verifier 日志信号。它尚不会构建镜像、启动容器或执行 verifier smoke test。

## 要解决的问题

Terminal-Bench 的一次运行失败，未必说明 Agent 能力不足：

| 现象 | 容易得出的错误结论 | 基于证据的正确结论 |
| --- | --- | --- |
| Docker 镜像无法构建 | Agent 失败了 | Agent 尚未获得可运行环境，任务被阻塞 |
| verifier 所需命令不存在 | Agent 没修好任务 | 任务镜像不满足其执行契约 |
| 容器因磁盘耗尽退出 | 新 Agent 版本退化了 | 评测基础设施发生故障 |
| 环境和 verifier 均健康，但最终测试失败 | 基础设施不可靠 | Agent 未能完成该任务 |

如果不能区分这些情况，团队可能报告失真的通过率、定位错误的回归原因，或发布根本无法可靠评测的 benchmark 任务。

## 面向哪些用户

- **Agent 框架开发者**：比较 prompt、模型、工具或运行时改动的影响。
- **模型与 Agent 研究者**：需要可重复、可审计的 benchmark 结果。
- **Terminal-Bench 维护者与任务贡献者**：在共享任务前验证任务健康度。
- **内部评测流水线团队**：运营终端 Agent 评测基础设施的工程团队。

## 范围

首个 MVP 有意保持狭窄：仅支持官方 [Terminal-Bench](https://github.com/harbor-framework/terminal-bench) 任务格式。

它不是：

- 一个 benchmark 或 leaderboard。
- 一个 Agent 框架或 Agent runner。
- 一个通用 Docker 运维平台。
- 一个托管式可观测性产品，也不替代 trace 平台。

## 目标工作流

```text
Terminal-Bench 任务 + 本地 Docker 环境
                    |
                    v
              1. 评测前预检
                    |
                    v
           2. Agent 运行产物分析
                    |
                    v
       3. Markdown / JSON 诊断报告
```

1. **预检**：在运行 Agent 前确认任务是否具备可评测条件。
2. **分析**：结合任务元数据、容器日志、verifier 结果和运行产物分类结果。
3. **报告**：记录结论、支撑证据，以及最小复现命令。

## 计划中的 CLI 契约

以下 pre-alpha 接口已可从源码运行；在 `0.1.0` 前，其行为仍可能调整：

```bash
# 检查一个 Terminal-Bench 任务和本地执行环境。
agent-env-doctor check <task-id-or-directory>

# 分析一个已完成的 Agent 运行目录。
agent-env-doctor analyze <run-directory>

# 从运行目录重新分析并渲染适合 CI 的报告。
agent-env-doctor report <run-directory> --format markdown|json
```

这些命令不会执行 Agent。它们检查任务和运行产物，并判断结果能否被可信地解释为 Agent 评测结果。

## 计划中的结论分类

| 结论 | 含义 |
| --- | --- |
| `READY` | 任务环境与 verifier 足够健康，可以开始评测。 |
| `BLOCKED` | 镜像构建、依赖、权限或网络等预检问题阻止评测开始。 |
| `INFRA_FAILURE` | 运行中评测基础设施发生故障，例如容器启动、挂载、端口或资源耗尽。 |
| `VERIFIER_FAILURE` | verifier 已损坏、不稳定，或无法确定任务结果。 |
| `AGENT_FAILURE` | 环境与 verifier 的证据均健康，但 Agent 未完成任务。 |
| `INCONCLUSIVE` | 缺少必要日志或产物，无法可靠归因。 |

## MVP 检查项

pre-alpha 已实现：

- 可读取的 `task.yaml`、非空 `instruction`、Dockerfile 与测试资源存在性。
- Docker CLI 与 daemon 可用性。
- 用于归因的 JUnit XML、JSON 状态字段，以及部分文本日志信号。
- 含证据路径的 Markdown 或 JSON 报告；存在 Dockerfile 时包含 Docker 构建复现命令。

计划中，尚未实现：

- Docker daemon 可用性、镜像构建和容器启动。
- 任务文件、卷挂载、权限和必需环境变量。
- 主机资源，包括磁盘、内存、CPU 和必需端口。
- 任务的网络预期及可观察的网络故障。
- 任务镜像中的必需命令和运行时依赖。
- 不依赖 Agent 运行的 verifier smoke test。
- 用于归因的 JUnit XML、JSON/JSONL 结果、Docker 日志和任务产物。

## 示例输出

以下是当前报告结构的示意输出，具体文案在 pre-alpha 阶段仍可能变化：

```text
任务：repair-ci-config
结论：BLOCKED

[PASS] 必需任务文件存在
[PASS] 找到 Dockerfile
[PASS] 找到 tests 目录
[FAIL] PATH 中未找到 Docker CLI

为什么这不属于 Agent 失败：
  Docker 不可用，因此 Agent 未获得可运行环境。

复现命令：
  docker info

证据：
  tasks/repair-ci-config/task.yaml
```

## GitHub Actions Summary 示例

以下是计划中的 CI Summary 格式，尚未实现 GitHub Actions 摘要发布：

```markdown
## agent-env-doctor：评测归因

| 结论 | 任务数 |
| --- | ---: |
| READY | 76 |
| BLOCKED | 8 |
| VERIFIER_FAILURE | 4 |
| AGENT_FAILURE | 12 |

Agent 成绩：42 / 76 个可评测任务（55.3%）

主要阻塞原因：5 台评测 worker 上的 Docker daemon 不可用。
证据：`artifacts/agent-env-doctor/report.json`
```

## 技术方向

MVP 计划实现为本地优先的 Python CLI：

- [Typer](https://typer.tiangolo.com/)：命令行界面。
- [Rich](https://rich.readthedocs.io/)：终端报告。
- [Pydantic](https://docs.pydantic.dev/)：任务、运行和报告数据模型。
- [Docker SDK for Python](https://docker-py.readthedocs.io/)：环境检查。
- 标准 XML 解析或 JUnit 解析器：处理结果文件。
- `pytest`：工具自身的测试套件。

报告格式应保持可携带且本地可用：人类可读的 Markdown 和机器可读的 JSON。云端采集、密钥托管和托管仪表盘不在 v1 范围内。

## 路线图

- [x] 定义本地 Terminal-Bench 任务目录与通用运行产物适配层。
- [ ] 实现 Docker 镜像构建、容器启动、挂载、资源、依赖与 verifier smoke test。
- [x] 实现保守的、基于证据的结论分类。
- [x] 输出终端、JSON 与 Markdown 报告。
- [ ] 在 CI 中发布 GitHub Actions 摘要。
- [x] 为全部结论分类加入 fixture 驱动测试。

## 隐私与安全

终端任务和日志可能包含文件路径、环境变量、命令输出与凭据。目标 MVP 将在本地运行，并应在生成报告时脱敏常见的密钥模式。发布任务产物或报告前，请先审查其中是否含有敏感信息。

## 贡献

欢迎贡献。早期尤其需要 Terminal-Bench fixture 示例、失败模式报告，以及对归因模型的审阅。提交 Pull Request 前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

请通过 issue 或 discussion 提交最小复现任务、已去除密钥的日志、期望结论和实际结论。

## 参考资料

- [Terminal-Bench](https://github.com/harbor-framework/terminal-bench)：评测 Agent 在终端环境中完成任务的 benchmark。
- [Harbor Framework](https://harborframework.com/)：Terminal-Bench 所在的框架生态。
