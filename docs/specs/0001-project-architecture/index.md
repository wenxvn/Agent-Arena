# 项目技术架构

**Status:** Accepted
**Date:** 2026-08-17
**Decision type:** Standalone architecture decision

## Summary

Agent Arena 采用 Python 3.13 的本地单体结构，使用 uv 管理依赖，代码放在 `src/agent_arena` 包中。第一版只提供本地 CLI 和文件输出，先完成确定性的 Spaceship Escape 环境，再接入阿里云百炼的 OpenAI 兼容接口。环境、Agent、模型客户端、运行器、评估和提示词保持独立边界，所有模型输出先经过严格的数据校验。

## Context

这是一个用于学习和比较 LLM Agent 行为的个人入门项目。第一版需要同时具备可运行性、可重复性和可展示性，但不需要在线服务、用户系统或多人协作。核心实验是让 Agent 在部分可观测的确定性世界中观察、调用工具、处理反馈并完成多步目标。

项目当前没有业务源代码，主要开发语言是中文环境下的 Python。模型服务使用阿里云百炼，调用协议为 OpenAI 兼容接口。真实模型调用可能受网络、配额和输出格式影响，因此本地测试和持续集成必须能够在不调用真实模型的情况下稳定运行。

## Decision

采用一个本地运行的分层单体。模块在同一个 Python 进程中协作，通过明确的数据契约传递 `Action`、`Observation`、`WorldState` 和 Episode Trace。第一版不引入微服务、数据库、Web API、Docker、云部署、RAG、向量数据库、LangChain 或多 Agent 编排。

**Implementation skills:** none. The repository skill discovery found no relevant Python, uv, Typer, Pydantic, OpenAI SDK, pytest, Ruff, mypy, or GitHub Actions skill.

### Proposed stack

| Layer | Choice | Reason |
|---|---|---|
| Architecture pattern | Local layered monolith | The project is small, local, and experimental, so one process gives the lowest build and debugging cost while preserving module boundaries. |
| Language and runtime | Python 3.13 | Python matches the project goal and the selected ecosystem, while 3.13 is a current supported runtime. |
| Dependency management | uv with `pyproject.toml` and `uv.lock` | uv gives one fast, reproducible workflow for environment creation, dependency resolution, and command execution. |
| Package layout | `src/agent_arena` | The source layout prevents accidental imports from the repository root and makes installed package behavior match normal use. |
| Data contracts | Pydantic v2 models | Strict models provide one validation boundary for Actions, Observations, world configuration, settings, and trace records. |
| Model client | OpenAI Python SDK behind an `llm/` adapter | The SDK supports the OpenAI compatible Bailian endpoint, while the adapter keeps provider details out of Agent and Environment code. |
| Model configuration | `pydantic-settings`, local `.env`, and checked in `config/runtime.defaults.json` | A single validated settings model and explicit source precedence make endpoint, model, timeout, retry, and key configuration reproducible without putting secrets in source. |
| Default model behavior | `qwen3.7-plus` with reasoning disabled | The first benchmark needs comparable structured decisions, short `decision_reason` values, and no stored chain of thought. |
| Prompt storage | Versioned text files under `prompts/` | Prompts can be reviewed, diffed, and reproduced independently from Python implementation code. |
| Decision provider interface | `DecisionProvider` protocol with Bailian and Fake implementations | The Runner receives one injected decision provider, so the same Agent Loop supports deterministic tests and explicit real model runs. |
| World configuration | Versioned JSON with an explicit seed | A named world version and seed make episodes reproducible even though the first world is deterministic. |
| Episode runner | A bounded local runner | Each episode has a maximum of 30 steps and a 30 second request timeout, which keeps experiments finite and debuggable. |
| Retry policy | At most 2 retries for network errors, 429, and 5xx, with exponential backoff | Transient provider failures can recover without creating unbounded latency or duplicate episode actions. |
| Invalid Action policy | Strict Pydantic validation, one correction request, termination after 3 consecutive invalid outputs | The loop remains safe and observable when a model returns malformed or impossible actions. |
| CLI | Typer commands `run`, `benchmark`, and `verify-model` | A typed command interface makes the first version demonstrable, defaults to a safe Fake provider, and leaves room for a future `ui` command. |
| Trace and logging | Standard library `logging` plus structured Episode Trace | JSON traces support replay and comparison, while ordinary logs support local diagnosis. |
| Episode storage | One JSON file per episode; benchmark output in JSON and CSV | Human readable files are sufficient for the local experiment scale and easy to inspect in a repository demo. |
| Testing | pytest, Ruff, and mypy | The project needs behavior tests for world rules, formatting checks, and static checks at modest setup cost. |
| Continuous integration | GitHub Actions on push and pull request | CI runs dependency sync, Ruff, mypy, and pytest with deterministic fixtures and a Fake LLM, never a real provider call. |
| First release boundary | Local CLI and local file output only | This keeps the first learning loop small and avoids premature hosting, authentication, API, and deployment work. |
| Future UI | Streamlit deferred to Release 3 | The CLI and trace are enough to demonstrate the system while preserving a clear path to a visual showcase later. |

### Module boundaries

| Module | Owns | Must not own |
|---|---|---|
| `arena/` | Action, Observation, WorldState, tool execution, and termination rules | LLM calls, Agent policy, or UI |
| `worlds/` | Spaceship Escape configuration and world specific rules | The generic Agent loop or model client |
| `agents/` | Baseline policy, memory, and future planning or reflection policies | World mutation or trace file format |
| `llm/` | Provider client creation, request formatting, timeout, retry, and response parsing | World state or Agent strategy |
| `evaluation/` | Episode runner, trace persistence, metrics, and benchmark orchestration | Changing Agent decisions or world rules |
| `prompts/` | Versioned prompt text | Secrets or runtime configuration |
| `ui/` | Future presentation of worlds, traces, and metrics | Direct mutation of Environment internals |

### Core contracts

1. `Environment.step(action)` accepts the only command type an Agent may send and returns an execution result plus a new Observation.
2. An Agent receives an Observation, not the complete WorldState.
3. `DecisionProvider.decide(observation, prompt, correction)` returns a structured decision candidate. The Runner injects either `BailianDecisionProvider` or `FakeDecisionProvider`; no Environment or Agent policy imports the OpenAI SDK.
4. `FakeDecisionProvider` consumes an ordered, test supplied queue of valid Actions, malformed payloads, provider errors, or delays. It also records the Observation and correction flag passed to it. An exhausted queue is an explicit test failure, never an implicit real model fallback.
5. Every Action is validated before execution. The first invalid output gets one correction attempt. Three consecutive invalid outputs end the episode with an explicit failure reason.
6. A trace records the episode id, world version, seed, step number, allowlisted Observation fields, short `decision_reason`, validated Action, tool result, status, token usage when available, and latency. It never records API keys, raw requests, raw responses, exception bodies, or full reasoning content.
7. A Fake LLM and deterministic fixtures are the default for tests and CI. A real API smoke test is optional and must be explicitly invoked outside the normal CI path.
8. The model adapter sets the provider base URL, model name, API key, timeout, retry policy, and reasoning mode from the validated configuration object.

### Configuration and CLI contract

`RuntimeSettings` is the single configuration model. Its precedence is CLI option, then environment variable including local `.env`, then checked in `config/runtime.defaults.json`. The defaults file contains no secret and defines the default world, seed, output directories, step limit, timeout, retry settings, and model behavior. A selected provider determines which settings are required.

| Command | Provider behavior | Required inputs | Defaults and output | Exit code |
|---|---|---|---|---|
| `run` | `--provider fake` is the default. `--provider bailian` is explicit. | No positional input in the first version. | Defaults to `spaceship-escape`, `react`, seed `0`, and `runs/`. It writes one episode JSON file. | `0` after a trace is written, even for a task failure. Configuration or runner failures return nonzero. |
| `benchmark` | `--provider fake` is the default. `--provider bailian` is explicit. | Episode count must be positive. | Defaults to `spaceship-escape`, `react`, deterministic seeds starting at `0`, and `results/`. It writes one benchmark JSON and one CSV. | `0` after all requested outcomes are persisted. Invalid configuration or inability to start the run returns nonzero. |
| `verify-model` | Always uses Bailian and never falls back to Fake. | A valid Bailian endpoint and API key. | Prints only the configured model name and final text. | `0` only for a successful compatible response. Configuration, authentication, network, or protocol failure returns nonzero without printing sensitive content. |

`--provider bailian` requires `OPENAI_BASE_URL` and one API key. `OPENAI_API_KEY` is used when it is present. `DASHSCOPE_API_KEY` is used only as a fallback. If both exist and differ, startup fails instead of choosing silently. If both exist and match, `OPENAI_API_KEY` is used. `OPENAI_MODEL` defaults to `qwen3.7-plus` when omitted. Fake runs require no endpoint or key.

### Model response and invalid Action state machine

| Event | Counter change | Runner action | Trace event | Outcome |
|---|---|---|---|---|
| Valid structured Action | Reset consecutive invalid count to `0` | Call `Environment.step` | `action_validated` | Continue |
| Schema invalid primary response | Add `1` | Request one correction against the same Observation | `action_invalid` then `correction_requested` | Continue unless count is `3` |
| Schema invalid correction response | Add `1` | Start a new decision cycle with the same Observation and no additional correction for that cycle | `action_invalid` | Continue unless count is `3` |
| Third consecutive schema invalid response | Add `1` to reach `3` | End episode | `invalid_action_limit` | `invalid_action_limit` |
| Schema valid but Environment rejected Action | No change | Save the tool feedback as the next Observation | `action_rejected` | Continue |
| Provider error after retry budget | No change | End episode | `provider_error` | `provider_error` |

Only a validated Action resets the invalid counter. An Environment rejection is an ordinary world result, not malformed model output. Transport and provider errors do not change the invalid counter.

### Retry contract

Only `BailianDecisionProvider` retries. The OpenAI SDK client is constructed with `max_retries=0`. The adapter makes at most three total attempts, which means the first request plus two retries. Each attempt has a 30 second request timeout. Network transport failures, HTTP 429, and HTTP 5xx are retryable; all other HTTP 4xx responses and schema or protocol failures are terminal. Backoff is 1 second before retry one and 2 seconds before retry two. Retries happen before an Action exists, so no Environment action is duplicated.

### Trace and benchmark contracts

Trace and logs use allowlist models. Trace step records may contain the world supplied Observation summary, validated Action fields, world supplied result summary, enum status, integer counters, token counts, and latency. `decision_reason` is a maximum of 280 characters. Other text fields are capped at 1,000 characters. The writer applies key pattern redaction to every text field and never serializes raw request bodies, response bodies, request headers, exception bodies, or provider objects. Tests must inject secret like strings into error and decision paths and assert that they do not appear in logs or traces.

A benchmark has a generated `benchmark_id` and produces a JSON manifest plus one CSV row per persisted episode, ordered by `episode_index`. Required row fields are `benchmark_id`, `episode_id`, `episode_index`, `world_version`, `seed`, `agent`, `provider`, `outcome`, `steps`, `invalid_output_count`, `rejected_action_count`, `latency_ms`, `input_tokens`, and `output_tokens`. The JSON manifest contains these rows and aggregate values: `attempted`, `succeeded`, `success_rate`, `mean_steps`, `mean_latency_ms`, and `mean_invalid_output_count`. `success_rate` is `succeeded / attempted`; every persisted terminal outcome, including provider failures, is part of the denominator.

### Derived runtime values

| Value | Source |
|---|---|
| Provider endpoint | `OPENAI_BASE_URL` loaded by `pydantic-settings` |
| API credential | `OPENAI_API_KEY` or `DASHSCOPE_API_KEY` loaded locally and never serialized |
| Model name | `OPENAI_MODEL`, defaulting to `qwen3.7-plus` |
| Episode step limit | `config/runtime.defaults.json`, environment override, or CLI option, default 30 |
| Request timeout | `config/runtime.defaults.json`, environment override, or CLI option, default 30 seconds per attempt |
| Retry count and backoff | `config/runtime.defaults.json`, environment override, or CLI option, default 2 retries with 1 and 2 second backoff |
| World version | Selected versioned JSON world configuration |
| Seed | CLI or configuration input, recorded in every trace |
| Trace file path | Local output directory plus generated episode id |
| Benchmark metrics | Derived only from stored Episode Trace records |

### Security and data handling

The API key is local configuration only. `.env` is ignored by Git and `.env.example` contains names and safe placeholders only. Keys must not appear in source, prompt files, logs, traces, test fixtures, commit messages, or user facing output. The adapter must avoid logging request headers and raw provider responses. Reasoning content is disabled by default and is not persisted; only a short decision reason is retained for inspection.

## Consequences

The project gets a small, reproducible end to end learning loop with clear seams for MemoryAgent, benchmark analysis, and a later Streamlit view. Deterministic fixtures make world bugs distinguishable from model variability. The same Agent protocol can be exercised with Fake LLM and real Qwen calls.

The tradeoff is that local JSON files do not provide concurrent access, query indexing, or multi user history. Files must be written through a temporary sibling file followed by an atomic rename, and episode ids must be UUID based to avoid collisions and partially written traces. The CLI is less immediately visual than a web interface, and a provider adapter adds some code before the first real model call. Disabling reasoning content makes traces less explanatory than full internal model output, but protects sensitive reasoning and keeps comparisons focused on observable decisions.

Python 3.13 may expose a dependency compatibility gap, so the lock file and CI must use that exact version before a dependency is accepted. uv requires lock file update discipline whenever dependencies change. Pydantic proves that an Action has the right shape, but only Environment rules prove it is executable in the current world. Real provider calls remain variable in cost, rate limit behavior, and latency, so a manual smoke test needs an explicit small request budget and must not be used to judge benchmark regressions.

## Follow-up

1. `/develop` should derive the Foundation scaffold from this spec, then implement and test the deterministic Spaceship Escape slice before enabling real model calls.
2. `/architect Spaceship Escape 环境` should define the exact room graph, tools, invalid action semantics, and victory conditions.
3. `/architect ReactAgent 与 Agent Loop` should define prompt inputs, structured Action output, correction behavior, and loop state transitions.
4. `/architect MemoryAgent` should define memory fields and fair comparison rules before Release 2.
5. A future UI spec should define Streamlit behavior only after CLI traces and benchmark outputs are stable.
6. The optional real API smoke test must remain manual or separately triggered, with an explicit budget and secret handling review.

## References

### Project sources

* `AGENTS.md`, persistent workflow and architecture constraints.
* `docs/architecture.md`, stable module boundaries and data flow.
* `docs/scope/scope.md`, release order and skateboard delivery approach.

### Practices and standards

* Layered monolith first for a small team and local workload.
* Strict schema validation at external boundaries.
* Deterministic fixtures and dependency injection for reliable tests.
* Structured logging with secret redaction.

### Links

* Python version status: https://devguide.python.org/versions/
* uv project layout: https://docs.astral.sh/uv/concepts/projects/layout/
* OpenAI Python SDK client: https://github.com/openai/openai-python/blob/main/src/openai/_client.py
* Alibaba Cloud Bailian OpenAI compatible chat API: https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions
* pytest getting started: https://docs.pytest.org/en/stable/getting-started.html
* Ruff formatter: https://docs.astral.sh/ruff/formatter/
* mypy getting started: https://mypy.readthedocs.io/en/stable/getting_started.html
* GitHub Actions documentation: https://docs.github.com/en/actions
