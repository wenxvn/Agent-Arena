# MAP-27 Phase 1 测试用例草案

- `test_two_hand_plans_complete_with_distinct_resource_ledgers`: 策略A tick25/电0/氧3/充一次；策略B tick20/电2/氧6/不充。
- `test_cargo_never_exceeds_two_slots_on_valid_plans`: 维修盒先被消耗或医疗包先被消耗后才装下一件。
- `test_over_capacity_load_is_rejected_without_mutation`: 第三件装载返回`CARGO_CAPACITY_EXCEEDED`。
- `test_charge_cell_is_one_use_and_battery_is_capped`: 电量13时只加到14，第二次请求无效且不增加电量。
- `test_remote_rescue_requires_relay_and_stabilized_survivor`: 两个前置条件缺一都返回具体错误码、不把状态设为RESCUED。
- `test_long_remote_road_can_strand_vehicle_without_charge`: F03抵E只剩1电，最短返B需2电，车辆被困。
- `test_sample_container_returns_sealed_sample_without_extra_cargo_slot`: 采样不凭空增加货位。
- `test_seed0_same_state_and_oracle_replay`: 相同seed和手写动作重复生成相同逐步Observation与Oracle字节。
- `test_submit_requires_all_objectives_and_positive_oxygen`: 少任一目标或氧气为0均不记成功。
