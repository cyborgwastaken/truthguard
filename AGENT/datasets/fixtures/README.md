# Fixture Documents — Labeled Cases

This directory contains 26 fictional documents for TruthGuard testing.
All content is invented. No real company names or real people's data are used.
The company used in these documents is **Acme Corp** (fictional).

## Case Labels

| Case ID | Question | Document(s) | Expected Outcome | Reason |
|---|---|---|---|---|
| C01 | How many days per week can employees work remotely? | `remote_policy_v1`, `remote_policy_v2` | `resolved` | v2 officially supersedes v1 with a later effective date; answer is 3 days. |
| C02 | What is the daily domestic travel budget? | `travel_budget_v1`, `travel_budget_v2` | `resolved` | v2 officially supersedes v1; current limit is $200/day. |
| C03 | What is the equipment allowance for new full-time employees? | `equipment_allowance_v1`, `equipment_allowance_v2` | `resolved` | v2 supersedes v1 with a later effective date; allowance is $2,000. |
| C04 | How many days of annual leave do employees receive per year? | `annual_leave_policy_v1`, `annual_leave_policy_v2` | `resolved` | v2 supersedes v1; answer is 25 days. |
| C05 | How long do employees have to submit expense receipts? | `expense_receipt_deadline_finance`, `expense_receipt_deadline_hr` | `conflict_unresolved` | Two equally official documents (Finance says 14 days, HR says 30 days); neither supersedes the other. |
| C06 | Can employees use co-working spaces without VPN? | `remote_coworking_policy_a`, `remote_coworking_policy_b` | `conflict_unresolved` | IT Security prohibits it; Operations allows it on certified networks. Both official, same date, no supersession. |
| C07 | How many days of unused leave can employees carry over, and is excess paid out? | `leave_carry_over_conflict_a`, `leave_carry_over_conflict_b` | `conflict_unresolved` | Payroll says 5 days with cash payout; HR says 10 days and no payout. Both official, same date, no supersession. |
| C08 | What is Acme Corp's policy on employee stock options? | *(none)* | `insufficient_evidence` | No document in the corpus mentions stock options. |
| C09 | Does Acme Corp offer a sabbatical programme? | *(none)* | `insufficient_evidence` | No document in the corpus mentions sabbaticals. |
| C10 | What is the company policy on gym membership reimbursement? | *(none)* | `insufficient_evidence` | No document covers gym or wellness reimbursement. |
| C11 | How many remote days per week can managers take versus interns? | `remote_work_managers`, `remote_work_interns` | `resolved` (two separate answers) | These are different employee groups with different rules — not a contradiction. Managers: 2 days. Interns: 0 for first 3 months, then standard. |
| C12 | What is the meal allowance for domestic travel versus international travel? | `meal_allowance_domestic`, `meal_allowance_international` | `resolved` (two separate answers) | Separate allowances for separate travel types — not contradictory. Domestic: $50/day. International: $75/day. |
| C13 | Can employees now work fully remotely with no office attendance requirement? | `remote_policy_v3_draft`, `remote_policy_v2` | `resolved` | The v3 document is only a draft with no effective date; it has no policy force. Current official policy (v2) says 3 days max. |
| C14 | Has the Operations Division expense limit for client entertainment been raised to $250? | `expense_limit_increase_draft`, `expense_policy_ops` | `resolved` | The draft proposing $250 has not been approved; the official limit of $150 in `expense_policy_ops` remains in effect. |
| C15 | How many days of paid parental leave does a primary caregiver receive? | `parental_leave_policy` | `resolved` | Single clear document: 16 weeks. |
| C16 | How many paid sick days do employees get per year? | `sick_leave_policy` | `resolved` | Single clear document: 10 days. |
| C17 | How often does Acme Corp refresh employee laptops? | `laptop_refresh_policy` | `resolved` | Single clear document: every 3 years. |
| C18 | What is the equipment allowance for contractors? | `contractor_equipment_informal`, `equipment_allowance_v1` | `resolved` | Both agree: contractors get $500 allowance; the informal note also says bring your own device but does not contradict the $500 figure. |

## Case Type Summary

| Case Type | Cases | Document IDs |
|---|---|---|
| Superseded (resolved by supersession) | C01, C02, C03, C04 | remote v1→v2, travel v1→v2, equipment v1→v2, leave v1→v2 |
| Unresolved conflict (equally official, no supersession) | C05, C06, C07 | expense deadlines, co-working, leave carry-over |
| Insufficient evidence | C08, C09, C10 | (no matching docs) |
| Hard negative (similar topic, different scope, no real conflict) | C11, C12 | managers vs interns, domestic vs international |
| Plain answerable (single clear source) | C15, C16, C17 | parental leave, sick leave, laptop refresh |
| Trap (draft document — newest is NOT authoritative) | C13, C14 | remote v3 draft, expense draft |

## Document Inventory

| document_id | authority_level | supersedes_document_id | effective_date |
|---|---|---|---|
| remote_policy_v1 | official | — | 2026-01-15 |
| remote_policy_v2 | official | remote_policy_v1 | 2026-04-15 |
| remote_policy_v3_draft | draft | — | null |
| remote_work_managers | official | — | 2026-05-01 |
| remote_work_interns | official | — | 2026-05-01 |
| remote_coworking_policy_a | official | — | 2026-02-15 |
| remote_coworking_policy_b | official | — | 2026-02-15 |
| travel_budget_v1 | official | — | 2025-11-01 |
| travel_budget_v2 | official | travel_budget_v1 | 2026-04-01 |
| meal_allowance_domestic | official | — | 2026-01-01 |
| meal_allowance_international | official | — | 2026-01-01 |
| expense_policy_ops | official | — | 2026-02-01 |
| expense_policy_sales | official | — | 2026-02-01 |
| expense_receipt_deadline_finance | official | — | 2026-03-01 |
| expense_receipt_deadline_hr | official | — | 2026-03-01 |
| expense_limit_increase_draft | draft | — | null |
| equipment_allowance_v1 | official | — | 2025-09-01 |
| equipment_allowance_v2 | official | equipment_allowance_v1 | 2026-07-01 |
| contractor_equipment_informal | informal | — | null |
| laptop_refresh_policy | official | — | 2025-10-01 |
| annual_leave_policy_v1 | official | — | 2025-06-01 |
| annual_leave_policy_v2 | official | annual_leave_policy_v1 | 2026-01-01 |
| leave_carry_over_conflict_a | official | — | 2026-07-01 |
| leave_carry_over_conflict_b | official | — | 2026-07-01 |
| parental_leave_policy | official | — | 2025-08-01 |
| sick_leave_policy | official | — | 2025-08-01 |
