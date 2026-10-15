# MAP-29 Phase 1 测试用例草案

- `test_npcs_use_fixed_seed_answer_tables_only`: 同NPC、同问题、同seed回答ID和载荷完全一致。
- `test_open_account_exposes_distinct_bias_models`: A错时、B隐地点、C仅声型、D仅泛问时不直接给索引。
- `test_each_valid_ask_consumes_one_global_question_and_one_tick`: 八次有效问题后额度为零。
- `test_ninth_ask_is_free_rejection_without_answer`: 返回`QUESTION_BUDGET_EXHAUSTED`且不再耗预算或tick。
- `test_repeated_question_costs_budget_without_new_answer`: 答案不漂移、唯一答案不增长。
- `test_investigation_and_comparison_do_not_spend_question_budget`: 物证与比对走独立机制。
- `test_A_bias_and_B_concealment_require_specific_comparison_evidence`: 缺少现场/档案支持不能标记不可靠。
- `test_C_honest_knowledge_limit_is_not_a_lie`: 不能凭不知道时地判为不可靠。
- `test_broad_and_high_information_plans_both_succeed`: 分别用7/3个问题正确指出时地和甲。
- `test_physical_fact_never_changes_after_false_testimony`: B说地点L后，Y撞针仍固定记录庭院事件。
- `test_same_seed_public_oracle_is_byte_stable`: seed0重复生成公开轨迹一致。
