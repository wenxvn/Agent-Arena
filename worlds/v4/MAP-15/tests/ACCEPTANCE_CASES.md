# MAP-15 运行时实现后验收用例

当前仅为待执行设计用例，不是pytest结果，也没有运行时环境。

1. Reset seed0：A、tick0、4次错误资源；只显示A墙色与本室三个临时槽位。
2. 逐动作复核 `oracle_trace.jsonl` 的两条成功路线：显式假设路线 tick4/资源4/零测试错；隐式恢复路线 tick5/资源3/一次测试错。
3. 检查 `inspect_symbols`、合法 `record_rule` 不推进tick；记录错误公式不获正确性反馈，且不能引用未见样例或重复记录。
4. 同墙色异相位：A/B红墙时目标随tick0/1变红/蓝；C/T金墙时按tick2/3变金/绿。
5. 任一错误有效门选择先按动作前tick判定，再推进tick、扣资源；失败反馈不包含正确门色。
6. F01、F02、F03应分别以 `RESOURCE_DEPLETED`、`RESOURCE_DEPLETED`、`TEST_WRONG_LIMIT` 终止，逐tick符合 `failure_traces/cases.yaml`。
7. B01最后资源边界：从初态可达；第二次测试区错误后资源与测试错误数同时达到0与2，按规格顺序以 `RESOURCE_DEPLETED` 终止。
8. 检查越界槽位、尚未观察即选择、非法规则ID与无效样例引用均无tick/资源变化。
9. 同动作序列固定seed0重复两次：每步Observation、样例日志、位置、预算、终止码及最终状态hash完全相同。
10. 不存在未来区域门色或裁判目标色字段；`oracle_trace.jsonl` 与 `failure_traces/` 内容不得输入Agent prompt/Observation。
