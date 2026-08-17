# Agent Arena

## Project state

- The project is at the planning stage. No application code or architecture spec exists yet.
- The product definition is in `总纲.md`.
- The ordered delivery state is in `docs/scope/scope.md`. Its first unticked item is the source of truth for the next task.
- Current first task: `/architect 项目技术架构`, then build and test a manually solvable deterministic Spaceship Escape environment before connecting an LLM.

## Stack

- **Language / Runtime**: Python, version and package manager are decided by the architecture spec.
- **LLM provider**: Alibaba Cloud Bailian, OpenAI compatible API.
- **Model**: `qwen3.7-plus`.
- **Configuration**: `.env` is local only. Copy `.env.example` when setting up another machine. Never commit, print, or put an API key in source, logs, traces, docs, tests, or prompts.

## Model configuration

- `OPENAI_BASE_URL` is the Bailian OpenAI compatible base URL.
- `OPENAI_API_KEY` is the runtime key used by the OpenAI client. `DASHSCOPE_API_KEY` is retained as the provider named alias.
- `OPENAI_MODEL` is the only default model name. Model calls must read these values from environment variables.
- Run `bash scripts/verify_model.sh` after changing local credentials or endpoint settings. It makes one small chat completion request.

## Build approach

Skateboard. Ship the smallest usable whole first: a deterministic environment, a baseline Agent Loop, a trace, and a reproducible result. Add memory, benchmark analysis, and UI only after that loop works.

## Resume protocol

At the beginning of every new conversation or task:

1. Read this file, `docs/scope/scope.md`, and the relevant file in `docs/specs/`.
2. Run `git status --short --branch` and inspect uncommitted work before editing.
3. Continue from the first unticked scope item. Do not start a later feature unless its dependencies are done or a documented decision says otherwise.
4. After implementation, run the required checks, update the scope through its owning skill, run `/sync`, then commit and push only the intended files.
5. Keep durable decisions in `docs/specs/`, delivery state in `docs/scope/`, and conventions in this file. Do not rely on chat history.

## Skill routing

| Situation | Call | Expected outcome |
|---|---|---|
| New product scope, next milestone, or reprioritization | `/scope` | Create or reconcile `docs/scope/scope.md` |
| Stack, model client, environment rules, data model, or any load bearing decision | `/architect <feature>` | Create or update a decision spec in `docs/specs/` |
| New project context, missing conventions, or a new meaningful code area | `/audit` or `/audit <area>` | Create or gap fill `AGENTS.md` context |
| Build an approved feature or a straightforward task with no unresolved design | `/develop <feature>` | Implement the scoped work and advance its build state |
| Code behavior is broken, a test fails unexpectedly, or verification exposes a defect | `/debug <symptom>` | Reproduce, diagnose, minimally fix, and verify the root cause |
| Tests are needed for uncommitted code | `/test <feature>` | Write behavior focused regression and edge case tests |
| Prove the feature works in the real app | `/check verify <feature>` | Verify acceptance criteria against the implementation |
| Review the diff before a PR or important push | `/check review` | Produce ranked review findings without editing code |
| Write a PR description, changelog, release note, or postmortem | `/document <type>` | Produce human facing change documentation from the diff |
| A feature is complete, after merge, or when durable context may be stale | `/sync` | Reconcile scope, specs, and AGENTS context from repository evidence |

## Default feature flow

`/scope` → `/architect` when a decision is needed → `/develop` → `/check verify` → `/test` → `/check review` for important changes → `/sync` → commit and push.

For a defect use `/debug` → `/test` → `/check verify` → `/sync`. For documentation only use `/document` after the relevant commit or diff exists.

## Project rules

- The Agent only receives `Observation`, never the full `WorldState`.
- Keep environment, agents, model client, evaluation, and UI separate.
- The environment is deterministic and covered by tests before benchmark results are trusted.
- Keep one Action schema and validate all LLM output before execution.
- Persist one JSON episode trace per run. Do not store secrets in traces.
- Do not introduce LangChain, vector databases, multi agent orchestration, RAG, database storage, or complex UI in the first MVP.
- Generated `runs/` and `results/` output is local and ignored by Git unless a future scope item explicitly changes that rule.

_This file is the durable entry point for new agents and conversations. Update it through `/audit` or `/sync` when a project wide fact changes._
