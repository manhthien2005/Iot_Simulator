# Bugfix Report: Pre-model Risk Engine

**Date:** 2026-05-06  
**Branch:** `refactor/fall-health-architecture-fixes`  
**Scope:** `pre_model_trigger/`, `api_server/dependencies.py`

---

## Tóm tắt

6 trong 10 lỗi được xác minh và sửa. Các lỗi còn lại (#7 context policy, #9 race condition model call, #10 audit trail) được ghi nhận là kỹ thuật nợ và cần scope riêng.

---

## Các thay đổi đã thực hiện

### Fix #1 + #2 — Field name mismatch + Derived metrics chưa tính

**File mới:** `pre_model_trigger/normalization.py`

**Vấn đề:**  
Simulator phát payload với field `respiratory_rate`, `temperature`, `blood_pressure_sys`, `blood_pressure_dia`, `activity_label` — nhưng `rules_config.json` và `RuleEngine` kỳ vọng `resp_rate`, `body_temp`, `sys_bp`, `dia_bp`, `activity_level`. Không có bước compute `pulse_pressure` và `map_val`.

**Fix:**  
Tạo `normalize_vitals_for_rules(vitals)` làm lớp translate field + compute derived metrics:

| Simulator field | Rule engine field |
|---|---|
| `respiratory_rate` | `resp_rate` |
| `temperature` | `body_temp` |
| `blood_pressure_sys` | `sys_bp` |
| `blood_pressure_dia` | `dia_bp` |
| `activity_label` | `activity_level` |
| *(computed)* | `pulse_pressure = sys_bp - dia_bp` |
| *(computed)* | `map_val = dia_bp + (sys_bp - dia_bp) / 3` |

---

### Fix #3 — Data quality không được enforce

**File mới:** `pre_model_trigger/normalization.py`  
**File sửa:** `pre_model_trigger/orchestrator.py`

**Vấn đề:**  
`rules_config.json` khai báo `data_quality.drop_or_hold_if_invalid = true` và `minimum_signal_quality_score = 0.7` nhưng không có code enforce. Sensor lỗi hoặc signal quality thấp vẫn đi qua rule evaluation.

**Fix:**  
- Thêm `validate_data_quality(vitals)` trong `normalization.py` kiểm tra:
  - Missing required fields
  - Non-numeric values
  - `signal_quality_score < 0.7`
  - `sensor_error_flag == True`
- Wired vào `TriggerOrchestrator.evaluate_tick()` làm Step 0b: nếu invalid thì skip vitals rule evaluation và trả `TriggerActionItem` type `"log"`. Fall trigger vẫn chạy (motion-based, không phụ thuộc vitals).

---

### Fix #4 — Time-series rules config/code mismatch (partial)

**File sửa:** `pre_model_trigger/health_rules/rules_config.json`  
**File sửa:** `pre_model_trigger/rule_engine.py`

**Vấn đề:**  
`persistent_drift` rules dùng text như `"heart_rate > 100 for >= 10 minutes at rest"` nhưng `_evaluate_time_series_rules()` kỳ vọng structured keys `metric`, `direction`, `threshold`, `window`.

**Fix:**
- Hai rule không cần baseline đã được convert sang structured format:
  - `HR_PERSISTENT_HIGH_AT_REST`: `heart_rate > 100` sustained 10 readings
  - `RR_PERSISTENT_HIGH_AT_REST`: `resp_rate >= 20` sustained 10 readings
- Các rule baseline-dependent đã được chuyển sang `pending_baseline_drift` (không bị evaluate, không bị skip âm thầm).
- Thêm direction `above_eq` / `below_eq` vào code để hỗ trợ `>=` / `<=` thresholds.

> **Lưu ý:** 7 rule baseline-dependent còn lại cần triển khai baseline tracking trước khi có thể convert.

---

### Fix #5 — Combination rules chưa được execute

**File sửa:** `pre_model_trigger/rule_engine.py`

**Vấn đề:**  
`rules_config.json` có section `combination_rules` đầy đủ (7 rules nguy hiểm như `spo2 <= 94 and resp_rate >= 20`) nhưng `RuleEngine.evaluate()` không có Phase 4 và không có method `_evaluate_combination_rules`.

**Fix:**  
- Thêm `_eval_multi_metric_condition(condition_str, vitals)` — evaluator giải quyết cả hai vế từ vitals dict.
- Thêm `_evaluate_combination_rules(vitals)` method trong `RuleEngine`.
- Gọi trong `evaluate()` như Phase 4.
- Các rule được evaluate: `HR_RR_HIGH_COMBINATION`, `SPO2_RR_COMBINATION`, `TEMP_HR_COMBINATION`, `SBP_HR_COMBINATION`, `SBP_MAP_COMBINATION`, `HR_RR_BORDERLINE_COMBINATION`, `SPO2_DBP_BORDERLINE_COMBINATION`.

---

### Fix #6 — Profile escalation reason_code mismatch

**File sửa:** `pre_model_trigger/rule_engine.py`

**Vấn đề:**  
`_apply_profile_adjustments()` so sánh `action.reason_codes` với profile output codes như `PROFILE_ESCALATED_HR_BORDERLINE` — nhưng instant rules tạo ra `HR_BORDERLINE_HIGH`. Hai set này không bao giờ giao nhau → escalation không bao giờ xảy ra cho người dùng high-sensitivity.

**Fix:**  
- Thêm `_PROFILE_ESCALATION_SOURCE_MAP` constant: map từ profile output code → source instant code.
- Sửa `_apply_profile_adjustments()` để build reverse map và match theo source code.
- Khi escalate, `reason_codes` của action được bổ sung thêm profile code (e.g., `HR_BORDERLINE_HIGH` + `PROFILE_ESCALATED_HR_BORDERLINE`).

---

### Fix #8 — `enable_model_calls` architecture không rõ ràng

**File sửa:** `api_server/dependencies.py`

**Vấn đề:**  
`TriggerOrchestrator` được khởi tạo với `enable_model_calls=False` (hardcoded) trong khi env `PRE_MODEL_TRIGGER_ENABLE_MODEL_CALLS` được đọc vào `_orch_enable_model_calls` nhưng không được truyền vào orchestrator.

**Fix:**  
Giữ `enable_model_calls=False` (intentional) và thêm comment giải thích rõ đây là **Architecture Option A**: orchestrator chỉ quyết định action severity, runtime `_trigger_risk_inference()` chịu trách nhiệm gọi model. `_orch_enable_model_calls` gates runtime path tại line 2823.

---

## Các lỗi chưa fix (scope riêng)

| Lỗi | Lý do chưa fix |
|-----|----------------|
| #4 (baseline-dependent drift rules) | Cần triển khai baseline tracking system |
| #7 Context policy chưa rõ | Cần design context detection flow riêng |
| #9 Race condition model call | Cần thay đổi API contract với HealthGuard backend |
| #10 Audit trail | Cần thiết kế TriggerDecisionAudit schema + storage |

---

## Flow sau khi fix

```
Raw vitals từ simulator
→ normalize_vitals_for_rules()    ← Fix #1 #2 (field mapping + derived metrics)
→ validate_data_quality()         ← Fix #3 (drop/hold nếu invalid)
→ push vào VitalsHistoryBuffer    (normalized)
→ evaluate instant rules          (instant_rules dùng đúng field names)
→ apply profile adjustments       ← Fix #6 (reason_code mapping đúng)
→ evaluate time-series rules      ← Fix #4 (structured format + above_eq)
→ evaluate combination rules      ← Fix #5 (phase mới)
→ select final severity
→ nếu SEND_TO_RISK_MODEL/URGENT + _orch_enable_model_calls=True
  → _trigger_risk_inference()     ← Fix #8 (architecture rõ ràng)
```

---

## Files thay đổi

| File | Loại | Mô tả |
|------|------|-------|
| `pre_model_trigger/normalization.py` | Tạo mới | normalize_vitals_for_rules + validate_data_quality |
| `pre_model_trigger/orchestrator.py` | Sửa | Wire normalization + data quality gate vào evaluate_tick |
| `pre_model_trigger/rule_engine.py` | Sửa | Combination rules, profile escalation fix, above_eq/below_eq |
| `pre_model_trigger/health_rules/rules_config.json` | Sửa | Structured persistent_drift + pending_baseline_drift |
| `pre_model_trigger/__init__.py` | Sửa | Export normalize_vitals_for_rules, validate_data_quality |
| `api_server/dependencies.py` | Sửa | Comment giải thích enable_model_calls=False architecture |
