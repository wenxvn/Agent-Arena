# MAP-28 Phase 1 测试用例草案

- `test_initial_observation_contains_no_culprit_or_future_evidence`: 初始只知王冠失踪。
- `test_evidence_is_revealed_only_at_its_room`: 锁、脚印、登记、目击各自只能在V/S/A/K查看。
- `test_record_requires_previously_observed_exact_evidence_id`: 猜ID或未到场不得写入笔记。
- `test_same_source_class_does_not_count_as_two_independent_sources`: 两份锁日志仍只算instrument_log一类。
- `test_every_claim_has_separate_support_gate`: 人物、路径、进入时间、离开时间各自验证两类支持。
- `test_witness_person_claim_is_corrected_by_registry_and_physical_trace`: Basil目击标签不得覆盖K3/C7独立信息。
- `test_exact_time_and_path_enums`: 21:05/21:07、21:13/21:15以及路径近义词均不匹配精确真值。
- `test_all_claims_correct_and_independently_supported`: 两条手写调查都成功提交同一四元组。
- `test_rejected_final_submission_does_not_disclose_truth_or_allow_retry`: 错/欠证一次终结，反馈不泄露答案。
- `test_same_seed_oracle_bytes_are_stable`: 固定seed0双次Oracle逐字节一致。
