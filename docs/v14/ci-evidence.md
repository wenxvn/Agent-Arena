# V14 远端 CI 证据

- 查询时间：2026-10-27（本地）
- 仓库：`wenxvn/Agent-Arena`
- 查询方式：GitHub REST API（未认证，只读）
  `GET /repos/wenxvn/Agent-Arena/actions/runs` 与 `/actions/runs/{id}/jobs`
- 本地未登录 `gh`（`gh auth login` 未配置），因此用 REST API 直接取证；**没有使用任何 Token**。

## 1. 最近 10 次 workflow 运行

| run ID | head SHA | 事件 | 结论 | 创建时间（UTC） |
|---|---|---|---|---|
| **40435185866** | `60c9ba2b64a3` | push | **success** | 2026-10-27T01:53:12Z |
| 40270247868 | `32e27826eab3` | push | success | 2026-10-26T04:40:11Z |
| 40268532905 | `54196e631e49` | push | success | 2026-10-26T04:20:05Z |
| 40267105974 | `7b9ee750c230` | push | success | 2026-10-26T04:03:42Z |
| 40267052820 | `3d94777e9449` | push | cancelled | 2026-10-26T04:03:03Z |
| 40256562719 | `e2d05855d84f` | push | success | 2026-10-26T01:55:35Z |
| 40202155255 | `81a58a0efffb` | push | success | 2026-10-25T14:25:23Z |
| 40188137046 | `4f7773bdea2c` | push | success | 2026-10-25T11:15:59Z |
| 39631507761 | `258eadc50393` | push | failure | 2026-10-21T16:04:53Z |
| 39525323249 | `4d6b3e9b5b70` | push | success | 2026-10-21T01:06:06Z |

## 2. 逐 job 结果（`lab-e2e` 是本轮关注对象）

| run ID | `quality` | `lab-e2e` | 备注 |
|---|---|---|---|
| 40435185866 | success（01:53:14→01:54:50Z） | **success**（01:53:14→01:54:21Z） | 当前 `main` HEAD |
| 40270247868 | success | **success** | — |
| 40268532905 | success | **success** | — |
| 40267105974 | success | **success** | — |
| 40256562719 | success | **success** | — |
| 40202155255 | success | **success** | — |
| 40188137046 | success | **success** | — |

**结论：`lab-e2e` 在最近 7 次独立远端运行中连续 7 次 `success`**，全部来自真实 CI 运行
（不同 commit，`run_attempt = 1`，不是重跑），且无需外部 Key、无需预装 Chromium
（workflow 内 `playwright install --with-deps chromium` 冷安装）。

> 注意：`40267052820` 是 `cancelled`，属于 concurrency 组自动取消（同一 ref 上更晚的 push），
> 不计入失败，也不计入成功证据。

## 3. 与提纲要求（连续三次成功）的对照

| 要求 | 实际 | 判定 |
|---|---|---|
| 至少 3 次独立远端成功 | 7 次 | **满足** |
| 列明 run ID 与 head SHA | 见上表 | 满足 |
| 冷安装 Chromium 稳定 | 7 次全部在 ~50s 内完成 E2E job | 满足（无重试步骤） |
| 无需外部 Key | workflow 未注入任何 secret | 满足 |

因此 Batch 10 可以执行 `continue-on-error: false`，并**以新的推送再验证一次**。
在本次改动推送后的运行结果出来之前，本文件把该条记为 `PENDING_VERIFICATION`。

## 4. 历史失败（保留，不掩盖）

`39631507761`（2026-10-21，`258eadc50393`）整体 `failure`：当时 workflow 只有 `quality` 一个 job，
失败步骤是"运行离线测试"，后续冻结/复算/验收步骤全部 `skipped`，且**尚无 `lab-e2e` job**。
保留在此是为了避免"永远绿色"的错觉。
