---
name: backlog-auditor
description: "Audit and review current JIRA sprint backlog progress by scanning _SPRINT.md and STORIES.md files. Generates progress tracking reports with completion rates and risk analysis. Triggers: check progress, review backlog, tiến độ sprint, kiểm tra backlog, sprint review, audit tasks."
category: project-management
risk: safe
source: custom
date_added: "2026-03-08"
---

# Skill: backlog-auditor — Sprint Review & Tracking

## Goal

Scan existing JIRA backlog files (`_SPRINT.md`, `_EPIC.md`, and `STORIES.md`) in `PM_REVIEW/Resources/TASK/JIRA/` to calculate completion metrics, identify blocked/at-risk items, and generate a comprehensive Vietnamese progress report in `PM_REVIEW/Task/`.

---

## Context Loading Protocol (MANDATORY)

> [!IMPORTANT]
> This skill relies solely on the JIRA folder structure. You do NOT need to read UC or SRS files for a backlog review.

### Tier 1: System Blueprint
1. **Read `PM_REVIEW/MASTER_INDEX.md`** — Basic context.
2. **Read `PM_REVIEW/Resources/TASK/JIRA/README.md`** — Discover which Sprints and Epics currently exist in the system.

### Tier 2: Progress Discovery
3. **Scan `_SPRINT.md` files** — Open `PM_REVIEW/Resources/TASK/JIRA/Sprint-{N}/_SPRINT.md` for active sprints. Count checked `[x]` vs unchecked `[ ]` Epic boxes.
4. **Scan `STORIES.md` files** — Open target Epic folders. Tally completed Acceptance Criteria checkboxes (`- [x]`) vs pending (`- [ ]`) to calculate granular completion percentage.

---

## Output Protocol & Constraints

- **Report Format**: Generate a Markdown report detailing the findings.
- **File Location**: Save exactly to `PM_REVIEW/Task/Backlog_Review_{YYYY-MM-DD}.md`.
- **Language**: All output (reports) MUST be in Vietnamese.
- 🚫 **DO NOT CREATE NEW TASKS**: This skill is READ-ONLY for the `JIRA` directory. It may only write to the `Task/` report directory.
- 🚫 **MANDATORY**: Ensure you check every single checkbox in every loaded `STORIES.md` to get an accurate tally.

---

## Example Output Structure

# Báo Cáo Tiến Độ Sprint — 08/03/2026

## Bảng Tổng Quan

| Sprint   | Tổng EP | Hoàn thành | Tỉ lệ Tiến độ tính theo SP |
| -------- | ------- | ---------- | -------------------------- |
| Sprint 1 | 6       | 2          | ~35%                       |
| Sprint 2 | 3       | 0          | 0%                         |

## ⚠️ Mục Có Rủi Ro / Cảnh Báo
- **EP04-Login (Sprint 1)**: 3/15 Acceptance Criteria hoàn thành. Đang chững lại ở phần Admin FE (S03).
- **EP12-Password (Sprint 1)**: Chưa bắt đầu (0/10 AC). Bị block bởi EP04?

## Phân Tích Stories Nổi Bật
*(Chi tiết các story đã xong và đang làm dở)*
