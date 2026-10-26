# 失败归因分层

- 局数：138；诊断条目：0
- 规则：主层按 PROVIDER > INTERFACE > MEASUREMENT > BUDGET > MECHANISM > POLICY 优先；接口与测量问题永远不算进能力分母。

## 主层分布

| 层 | 含义 | 局数 |
|---|---|---:|
| `INTERFACE_CONTRACT` | 接口/契约问题（不是能力） | 0 |
| `MEASUREMENT_COVERAGE` | 测量覆盖问题（不是能力） | 0 |
| `BUDGET_CENSORED` | 预算截尾（没测完） | 23 |
| `ENVIRONMENT_MECHANISM` | 环境机制真实触发但未达成 | 0 |
| `POLICY_BEHAVIOUR` | 策略可观察行为 | 0 |
| `PROVIDER` | Provider/基础设施 | 0 |
| `UNKNOWN` | 证据不足 | 77 |

## 逐局归因（带证据锚）

| run_id | 地图 | 实验臂 | 主层 | 证据步 | 摘要 |
|---|---|---|---|---|---|
| `web-20261026T040640Z-7af04226` | MAP-18 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T040745Z-566092ff` | MAP-18 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T040545Z-570cf40a` | MAP-18 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T040613Z-da993ad7` | MAP-18 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T040939Z-6e9f4ec7` | MAP-16 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T040948Z-411d5430` | MAP-16 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T040812Z-98e9bf7b` | MAP-16 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T041118Z-d2792797` | MAP-16 | `reflection.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T041003Z-d631bc8c` | MAP-16 | `reflection.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121005Z-9fc0657c` | MAP-16 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121015Z-833c5066` | MAP-16 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121034Z-e5a12d03` | MAP-16 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121107Z-c173aa5f` | MAP-16 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121251Z-b7fa4415` | MAP-16 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121408Z-f4d48c52` | MAP-16 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121415Z-5a1b6a05` | MAP-16 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121520Z-c854404e` | MAP-18 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121629Z-592eff81` | MAP-18 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121700Z-65d2d9ea` | MAP-18 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121719Z-a9cb7fe6` | MAP-18 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121743Z-91195341` | MAP-18 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T121946Z-3e5b3544` | MAP-18 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T122112Z-a3d780aa` | MAP-18 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T122153Z-7e38291a` | MAP-22 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T122520Z-cf621a41` | MAP-22 | `memory.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T122826Z-60d296a4` | MAP-22 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T123042Z-0d9cd8de` | MAP-22 | `basic.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T123304Z-4641a54e` | MAP-22 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T123428Z-e3958c47` | MAP-22 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T123757Z-691cec43` | MAP-22 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T125506Z-c1cbd46f` | MAP-30 | `basic.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T125936Z-be71b3c0` | MAP-30 | `memory.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T130325Z-026304b8` | MAP-30 | `planning.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T130926Z-dba13d2d` | MAP-30 | `basic.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T131224Z-80766e9c` | MAP-30 | `memory.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T131634Z-126c1c2a` | MAP-30 | `planning.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T131955Z-87d4d206` | MAP-30 | `basic.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T132410Z-acdcff4f` | MAP-30 | `memory.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T132740Z-90ace8a1` | MAP-30 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T011307Z-1a69cec6` | MAP-18 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T011328Z-c348044b` | MAP-18 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T011348Z-8c0465af` | MAP-18 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T153457Z-7b0f4175` | MAP-22 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T153631Z-794503d6` | MAP-22 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T153747Z-4b8e7abe` | MAP-22 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T153943Z-cf4ba029` | MAP-22 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T154121Z-f08fdd8a` | MAP-22 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T154232Z-ceded6e6` | MAP-22 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T154354Z-17909eb5` | MAP-22 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T154527Z-8908c090` | MAP-22 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T154656Z-b84720fc` | MAP-22 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T015753Z-9b141eb4` | MAP-22 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T020015Z-ca16ba71` | MAP-22 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T155152Z-7c8494ed` | MAP-30 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T155434Z-e29c01e5` | MAP-30 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T155813Z-331b0d91` | MAP-30 | `planning.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T160208Z-61a83e88` | MAP-30 | `basic.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T160908Z-6d0a02d9` | MAP-30 | `memory.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T161349Z-08de10ad` | MAP-30 | `planning.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261025T162006Z-162e26a2` | MAP-30 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T162508Z-6f12e2fb` | MAP-30 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261025T162641Z-42ac2741` | MAP-30 | `planning.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261026T001549Z-a9335fa1` | MAP-30 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T001838Z-50d9646c` | MAP-30 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T002106Z-82fd154f` | MAP-30 | `planning.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261026T002409Z-9146a35d` | MAP-30 | `basic.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261026T002742Z-9e78509c` | MAP-30 | `memory.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261026T003219Z-a932c2e7` | MAP-30 | `planning.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261026T003825Z-4a628709` | MAP-30 | `basic.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261026T004242Z-89ed4a7c` | MAP-30 | `memory.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261026T004946Z-40a762d2` | MAP-30 | `planning.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261026T020606Z-e5f002a0` | MAP-16 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T020617Z-b0b85d50` | MAP-16 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T020636Z-b643d309` | MAP-16 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T020704Z-062da438` | MAP-16 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T020716Z-ecf48698` | MAP-16 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T020921Z-33cfed1c` | MAP-16 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T020926Z-cd4e871c` | MAP-16 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T020938Z-34db1378` | MAP-16 | `planning.v1` | `BUDGET_CENSORED` | — | 预算/动作上限截尾（没有诊断规则命中）。 |
| `web-20261026T021321Z-f045a991` | MAP-18 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T021420Z-51d7dc43` | MAP-18 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T021454Z-a8db03de` | MAP-18 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T021510Z-1ebcd104` | MAP-18 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T021538Z-0540b602` | MAP-18 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T021610Z-5e3942d6` | MAP-18 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T021707Z-02bc7956` | MAP-18 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T012103Z-53a0bcd6` | MAP-16 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T012223Z-2cd8f607` | MAP-16 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T012237Z-b5df98ab` | MAP-16 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T012527Z-83560ccf` | MAP-16 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T012620Z-202bb46c` | MAP-16 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T012805Z-bbdc973b` | MAP-16 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T013251Z-c3acfcae` | MAP-18 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T013338Z-2dc259f0` | MAP-18 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T013432Z-478dce8b` | MAP-18 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T013524Z-4693dafc` | MAP-18 | `basic.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T013556Z-fae0ac82` | MAP-18 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T013613Z-41e5841c` | MAP-18 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T013700Z-be486165` | MAP-18 | `memory.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |
| `web-20261026T013720Z-b2c1544f` | MAP-18 | `planning.v1` | `UNKNOWN` | — | 没有命中任何确定性规则；证据不足。 |

## 未归因局（证据不足，不猜）

- `web-20261026T040640Z-7af04226`
- `web-20261026T040745Z-566092ff`
- `web-20261026T040545Z-570cf40a`
- `web-20261026T040613Z-da993ad7`
- `web-20261026T040939Z-6e9f4ec7`
- `web-20261026T040948Z-411d5430`
- `web-20261026T040812Z-98e9bf7b`
- `web-20261026T041118Z-d2792797`
- `web-20261026T041003Z-d631bc8c`
- `web-20261025T121005Z-9fc0657c`
- `web-20261025T121015Z-833c5066`
- `web-20261025T121034Z-e5a12d03`
- `web-20261025T121107Z-c173aa5f`
- `web-20261025T121251Z-b7fa4415`
- `web-20261025T121408Z-f4d48c52`
- `web-20261025T121415Z-5a1b6a05`
- `web-20261025T121520Z-c854404e`
- `web-20261025T121629Z-592eff81`
- `web-20261025T121700Z-65d2d9ea`
- `web-20261025T121719Z-a9cb7fe6`
- `web-20261025T121743Z-91195341`
- `web-20261025T121946Z-3e5b3544`
- `web-20261025T122112Z-a3d780aa`
- `web-20261025T122153Z-7e38291a`
- `web-20261025T122826Z-60d296a4`
- `web-20261025T123304Z-4641a54e`
- `web-20261025T123428Z-e3958c47`
- `web-20261025T123757Z-691cec43`
- `web-20261025T132740Z-90ace8a1`
- `web-20261026T011307Z-1a69cec6`
- `web-20261026T011328Z-c348044b`
- `web-20261026T011348Z-8c0465af`
- `web-20261025T153457Z-7b0f4175`
- `web-20261025T153631Z-794503d6`
- `web-20261025T153747Z-4b8e7abe`
- `web-20261025T153943Z-cf4ba029`
- `web-20261025T154121Z-f08fdd8a`
- `web-20261025T154232Z-ceded6e6`
- `web-20261025T154354Z-17909eb5`
- `web-20261025T154527Z-8908c090`
- `web-20261025T154656Z-b84720fc`
- `web-20261026T015753Z-9b141eb4`
- `web-20261026T020015Z-ca16ba71`
- `web-20261025T155152Z-7c8494ed`
- `web-20261025T155434Z-e29c01e5`
- `web-20261025T162006Z-162e26a2`
- `web-20261025T162508Z-6f12e2fb`
- `web-20261026T001549Z-a9335fa1`
- `web-20261026T001838Z-50d9646c`
- `web-20261026T020606Z-e5f002a0`
- `web-20261026T020617Z-b0b85d50`
- `web-20261026T020636Z-b643d309`
- `web-20261026T020704Z-062da438`
- `web-20261026T020716Z-ecf48698`
- `web-20261026T020921Z-33cfed1c`
- `web-20261026T020926Z-cd4e871c`
- `web-20261026T021321Z-f045a991`
- `web-20261026T021420Z-51d7dc43`
- `web-20261026T021454Z-a8db03de`
- `web-20261026T021510Z-1ebcd104`
- `web-20261026T021538Z-0540b602`
- `web-20261026T021610Z-5e3942d6`
- `web-20261026T021707Z-02bc7956`
- `web-20261026T012103Z-53a0bcd6`
- `web-20261026T012223Z-2cd8f607`
- `web-20261026T012237Z-b5df98ab`
- `web-20261026T012527Z-83560ccf`
- `web-20261026T012620Z-202bb46c`
- `web-20261026T012805Z-bbdc973b`
- `web-20261026T013251Z-c3acfcae`
- `web-20261026T013338Z-2dc259f0`
- `web-20261026T013432Z-478dce8b`
- `web-20261026T013524Z-4693dafc`
- `web-20261026T013556Z-fae0ac82`
- `web-20261026T013613Z-41e5841c`
- `web-20261026T013700Z-be486165`
- `web-20261026T013720Z-b2c1544f`
