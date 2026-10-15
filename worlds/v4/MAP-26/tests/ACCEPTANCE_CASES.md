# MAP-26 Phase 1 测试用例草案

- `test_initial_observation_is_seed_equivalent`: seed 0/1/2只显示`COMMUNICATION_LOST`，不显示seed或故障ID。
- `test_completed_test_reading_matches_fixed_seed_fixture`: 三个seed的每项测试读数与裁判夹具一致。
- `test_repeating_test_never_changes_reading`: 同一seed同一测试重复执行返回同值。
- `test_log_is_ambiguous_and_shared`: 日志不唯一指向故障，也不因seed变化泄漏真因。
- `test_wrong_replace_emits_component_feedback_and_consumes_one_spare`: 错换反馈仅说明刚测试部件通过而链路未恢复。
- `test_rollback_restores_wrong_spare_but_keeps_elapsed_time_and_retry_count`: 返还错误模块和原槽位，不返还tick、不返retry历史。
- `test_same_wrong_part_retry_cost_increases`: 同一错误part的错误替换持续时间依次为1、2、3……。
- `test_diagnose_first_and_feedback_correction_both_leave_one_spare`: seed0两条手工路线最终通信恢复并各余1枚。
- `test_spare_exhaustion_fails_immediately_while_link_down`: 第二枚错件消耗后立即失败。
- `test_correct_replacement_requires_restart`: 安装正确部件但重启前不满足成功谓词。
