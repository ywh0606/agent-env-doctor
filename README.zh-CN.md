# agent-env-doctor

**Pre-alpha**：面向终端 Agent 的 Terminal-Bench 环境预检与失败归因工具。

[English](README.md) | [Terminal-Bench](https://github.com/harbor-framework/terminal-bench) | [Harbor Framework](https://harborframework.com/)

`agent-env-doctor` 是一个本地开发者工具，用于回答仅凭 benchmark 分数无法回答的问题：

> 是 Agent 没有完成任务，还是任务环境先让 Agent 无法运行？

它计划在评测前检查 Terminal-Bench 任务环境，在运行后分析产物，并生成带证据的 Markdown 或 JSON 报告。目标是让终端 Agent 的评测可复现，且每次失败都能被合理归因。

## 项目状态

本仓库处于 **pre-alpha** 阶段，`0.2.0a1` 已提供可从源码运行的本地 Python CLI，供早期验证和反馈使用。现有检查项和产物解析器只覆盖规划 MVP 的一部分，并且在首个稳定版本前仍可能调整。请勿仅凭 pre-alpha 的结论发布 benchmark 结果。

项目采用 [Apache-2.0](LICENSE) 许可证。

### 从源码运行

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"

# 在 Terminal-Bench 检出目录中执行，或传入任务的绝对路径。
.venv/bin/agent-env-doctor check hello-world

# 显式启用镜像构建与 shell smoke 容器检查。
.venv/bin/agent-env-doctor check hello-world --build --artifacts-dir artifacts/doctor

# 还可检查镜像中的指定命令；--require-command 可重复使用。
.venv/bin/agent-env-doctor check hello-world --build \
  --require-command pytest \
  --require-command git

# 检查必需主机端口能否本地绑定；--require-port 可重复使用。
.venv/bin/agent-env-doctor check hello-world \
  --require-port 3000 \
  --require-port 8080
.venv/bin/agent-env-doctor analyze /path/to/agent-run --format json
```

默认情况下，`check` 会验证任务结构、Dockerfile/测试资源是否存在、Docker CLI 与 daemon 是否可用、主机磁盘/CPU 条件，以及指定的本地端口绑定；这些静态检查不会构建镜像或启动容器。启用 `--build` 后，它会构建任务镜像、以 `--network none` 启动 shell smoke 容器，并可在该镜像中检查每个 `--require-command` 指定的命令。`analyze` 会识别 JUnit XML、JSON 状态字段和部分基础设施/verifier 日志信号。它会先收集全部证据，再按 `INFRA_FAILURE`、`VERIFIER_FAILURE`、`AGENT_FAILURE`、`READY`、`INCONCLUSIVE` 的优先级分类；每个文本日志最多扫描 1 MB。

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

## CLI 契约

以下 pre-alpha 接口已可从源码运行；在首个稳定版本前，其行为仍可能调整：

```bash
# 仅运行静态检查（默认行为）。
agent-env-doctor check <task-id-or-directory>

# 显式启用 Docker 构建和 shell smoke 检查。
agent-env-doctor check <task-id-or-directory> --build \
  [--build-timeout <seconds>] \
  [--artifacts-dir <directory>] \
  [--keep-image] \
  [--require-command <command>]... \
  [--require-port <port>]...

# 分析一个已完成的 Agent 运行目录。
agent-env-doctor analyze <run-directory>

# 从运行目录重新分析并渲染适合 CI 的报告。
agent-env-doctor report <run-directory> --format markdown|json
```

这些命令不会执行 Agent。它们检查任务和运行产物，并判断结果能否被可信地解释为 Agent 评测结果。

`--build` 有意设计为显式开关，因为它会执行本地 Docker 工作。`--artifacts-dir`、`--keep-image` 与 `--require-command` 必须配合 `--build` 使用；每个 `--require-command` 值只能是一个可执行文件名或路径。提供 `--artifacts-dir` 时，构建和 smoke 输出会写入该目录。临时镜像默认会在检查后清理；传入 `--keep-image` 可保留镜像以便排查。`--build-timeout` 用于限制每个 Docker 操作的时长，`--require-command` 可重复传入，以便在 smoke 容器中检查多个命令。`--require-port` 可重复传入，用于检查每个端口能否在本机 `127.0.0.1` 上绑定；它不会启动服务。smoke 容器以 `--network none` 运行，但 Docker 镜像构建本身可能需要网络访问。

## 结论分类

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
- 主机磁盘与 CPU 检查；可用磁盘偏低会报告为警告。
- 通过 `check --build` 提供可选的 Docker 镜像构建与 shell smoke 容器检查。
- 通过重复的 `--require-command` 提供可选的镜像内命令检查。
- 通过重复的 `--require-port` 提供可选的本地主机端口绑定检查。
- smoke 容器禁用 Docker 网络（`--network none`）。
- 提供 `--artifacts-dir` 时捕获 Docker 构建与 smoke 输出。
- 默认清理临时构建镜像，并通过 `--keep-image` 支持调试保留。
- 用于归因的 JUnit XML、JSON 状态字段，以及部分文本日志信号。
- 含证据路径的 Markdown 或 JSON 报告；存在 Dockerfile 时包含 Docker 构建复现命令。

计划中，尚未实现：

- 任务文件、卷挂载、权限和必需环境变量。
- 主机内存检查。
- 任务的网络预期及可观察的网络故障。
- 不依赖 Agent 运行的 verifier smoke test。
- 用于归因的 JSONL 结果、Docker 日志和更多任务产物。

## 当前实现

此 pre-alpha 是一个本地优先的 Python CLI，使用：

- [Typer](https://typer.tiangolo.com/)：命令行界面。
- [Pydantic](https://docs.pydantic.dev/)：任务、运行和报告数据模型。
- [PyYAML](https://pyyaml.org/)：任务元数据。
- 一个基于子进程的轻量 Docker CLI 边界：执行构建、smoke 检查与清理。
- 标准库 XML 解析：处理 JUnit 结果文件。
- `pytest`：工具自身的测试套件。

报告格式应保持可携带且本地可用：人类可读的 Markdown 和机器可读的 JSON。云端采集、密钥托管和托管仪表盘不在 v1 范围内。

## 路线图

- [x] 定义本地 Terminal-Bench 任务目录与通用运行产物适配层。
- [x] 增加可选 Docker 镜像构建、隔离的 shell smoke 容器、必需命令/端口检查和构建产物。
- [ ] 实现挂载、权限、环境检查、主机内存、网络预期与 verifier smoke test。
- [x] 实现保守的、基于证据的结论分类。
- [x] 输出终端、JSON 与 Markdown 报告。
- [ ] 在 CI 中发布 GitHub Actions 摘要。
- [x] 为全部结论分类加入 fixture 驱动测试。

## 隐私与安全

终端任务和日志可能包含文件路径、环境变量、命令输出与凭据。目标 MVP 将在本地运行，并应在生成报告时脱敏常见的密钥模式。发布任务产物或报告前，请先审查其中是否含有敏感信息。

`check --build` 会在本机执行任务的 Docker 构建指令。仅对可信的任务定义使用它：镜像构建可能访问网络并执行构建期命令。后续 smoke 容器会以 `--network none` 隔离运行，但这种隔离不覆盖构建阶段。

## 贡献

欢迎贡献。早期尤其需要 Terminal-Bench fixture 示例、失败模式报告，以及对归因模型的审阅。提交 Pull Request 前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

请通过 issue 或 discussion 提交最小复现任务、已去除密钥的日志、期望结论和实际结论。

## 参考资料

- [Terminal-Bench](https://github.com/harbor-framework/terminal-bench)：评测 Agent 在终端环境中完成任务的 benchmark。
- [Harbor Framework](https://harborframework.com/)：Terminal-Bench 所在的框架生态。
