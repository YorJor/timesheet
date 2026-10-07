---
name: timesheet
description: Daily work log and monthly or weekly timesheet built from Claude Code chat history. Use when the user says "timesheet", "what did I work on", "log my day", "hours per project", or runs /timesheet:timesheet with setup, log or a date range. Writes hours per project plus a short task description to the user's work log folder.
argument-hint: "[setup | log | this month | last month | this week | last week | YYYY-MM-DD..YYYY-MM-DD]"
---

# Timesheet

Three jobs:
- **`setup`**: one-time setup on a new machine.
- **`log`**: bring the daily work log up to date. The daily scheduled task runs this every evening.
- **`[range]`** (anything else, or nothing): produce the timesheet, with hours per project per day and a short task description. The range is one of:
  - nothing, or `this month`: from the 1st of this month to today
  - `last month`: the whole previous calendar month
  - `this week`: Monday of this week to today
  - `last week`: the previous Monday to Sunday
  - `YYYY-MM-DD..YYYY-MM-DD`: any range, both days included

**Work log folder:** `${user_config.log_dir}`. Expand a leading `~` to the home folder. If that value is empty or still shows as a placeholder, use `~/Documents/worklog`. Below, LOG_DIR means this folder.

The facts come from the scan script bundled with this skill. It reads `~/.claude/projects` (the chat history) and prints JSON per day and project: `hours`, the work `blocks` (local times), `chats`, `chat_titles`, the user's `prompts`, `files_edited` and the user's own `git_commits`. Hours are time with Claude Code active, split by idle gaps over 15 minutes, with parallel chats in one project counted once.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/timesheet/scan.py" --log-dir "LOG_DIR" 2026-10-01 2026-10-07
```

## `setup`

Do each step, and skip any that is already done:
1. Create LOG_DIR.
2. **Chat history.** Claude Code deletes chats older than `cleanupPeriodDays` (30 by default). In `~/.claude/settings.json`, make sure `cleanupPeriodDays` is at least 60, so last month's timesheet never misses days. Don't lower a bigger value. Keep the rest of the file unchanged.
3. **Daily task.** If the `create_scheduled_task` tool is available (the Claude desktop app has it), create a task with taskId `daily-work-log`, title `Daily work log`, cronExpression `30 18 * * *`, notifyOnCompletion false, and this prompt:
   > Update my daily work log: run `/timesheet:timesheet log`. If that command is not available, say that the timesheet plugin is not installed and stop. Do not edit any other files, commit anything, or message anyone. Finish with one line listing the days written and their total hours.

   First check with `list_scheduled_tasks` that `daily-work-log` doesn't exist yet. If the tool is not available (for example in the terminal), say that the evening task needs the Claude desktop app, and that `/timesheet:timesheet` still works on its own for the last 60 days.
4. Run the `log` steps below once to fill in the past two weeks.
5. Reply with what was set up, where the log is, and: "Click **Run now** on Daily work log in the Scheduled section of the sidebar once, so its tool approvals are saved for the evening runs."

## Work log format

One file per month: `LOG_DIR/YYYY-MM.md`, starting with `# Work log · <Month YYYY>`. Days in date order, newest last. Each day is one section:

```markdown
## 2026-10-07 Wed
<!-- worklog 2026-10-07 status=final raw=5.03 -->

| Project | Hours | What I did |
|---|---:|---|
| Billing | 4.25 | Built the invoice export and fixed rounding in tax totals |
| No project folder | 0.75 | Set up Claude Code plugins |

**Total:** 5.00 h · 09:19–16:43

- **Billing:** CSV and PDF invoice export; tax totals round per line; tests for both. 6 commits.
- **No project folder:** installed plugins; set up this work log.
```

Rules for an entry:
- **Hours:** round each project to the nearest 0.25 h, with a minimum of 0.25 when there was any activity. The total is the sum of the rounded values. Put the unrounded day total in `raw=`.
- **What I did:** one short line per project, at most about 20 words, in plain task language a manager would recognize (features, fixes, reviews, documentation, setup). Base it only on the chat titles, prompts, edited files and commits. Never invent work. Skip filler such as "worked on". Write in English unless the user asks otherwise.
- **Bullets:** one per project with the concrete pieces of work, and the commit count if there were any.
- **Time range:** the first block start to the last block end.
- **No project folder:** keep this row. It is work done in chats without a project folder, often tooling or setup.
- **Status:** `status=final` for past days. For today use `status=partial as-of=HH:MM`, and add ` (partial, as of HH:MM)` to the heading.

## `log`

1. Work out the dates: the last 14 days up to today.
2. Read the month files covering them. A day needs writing when it has no section yet, or its marker says `status=partial`.
3. Run the scan script once over that whole range. Days with no activity get no section.
4. For each day that needs writing, write or replace its section, keeping days in date order. Replace a section from its `## ` heading up to the next `## ` heading or the end of the file. Never change a `status=final` section.
5. Create the month file and LOG_DIR if they are missing.
6. Reply in one or two lines: which days were written, and each day's total hours.

## Timesheet for a range

1. Run the `log` steps first, so the log is complete. If the range starts more than 14 days ago, also scan and write the missing days from the range's start. Then read the range from the month files. The log is the source of truth, and it keeps working after old chat history is deleted.
2. Build the timesheet:
   - **Summary:** one row per project with its total hours and days worked, and a final total row. Put this first.
   - **Hours tables:** one table per calendar week in the range (Monday to Sunday), headed with the week's dates. One row per project, one column per day (leave days without work, and days outside the range, empty), and a total column, with a final total row. A one-week range has a single table.
   - **Tasks by day:** a heading per day with work, in date order, such as `### Thu 1 Oct · 3.00 h`. Under it, one entry per project worked that day, written like a timesheet calendar entry:

     ```markdown
     - **[Billing] Invoicing: CSV + PDF invoice export; tax totals round per line** · 4.25 h
       Built the invoice export in CSV and PDF from the orders screen; tax totals now round per line instead of per invoice, matching the accounting report; added tests for both. 6 commits.
     ```

     - **Title line:** `[Project]`, then the area of work (the feature, module or deliverable, such as "AI Agent", "Data Access console" or "v1.1 documentation"), a colon, and the main pieces of work joined with ` + ` and `; `. Keep it to about 10 to 25 words, so it can be pasted into a calendar or timesheet tool as it is. Then ` · ` and the hours.
     - **Detail line:** the concrete work behind the title, in more detail than the title: features built, fixes, tests, documents, decisions and reviews, in plain words a manager would recognize, separated by semicolons. End with the commit count when there were commits. Base it only on the work log and the scan data. Never invent work.
   - Use the project folder names as they appear. If a project is "No project folder", say so, so the user can decide where it belongs.
   - If the range includes today, title it as partial, for example "October 2026 (1–7 Oct, so far)".
3. Save it in `LOG_DIR/timesheets/`, overwriting an earlier version of the same file:
   - a calendar month (`this month`, `last month`, nothing): `YYYY-MM.md`, for example `2026-10.md`
   - a week (`this week`, `last week`): `YYYY-Www.md` (ISO week), for example `2026-W41.md`
   - any other range: `<first>_<last>.md`
4. Show the timesheet in the reply, and the file path.
5. End with one line reminding the user that hours are time with Claude Code active, so meetings and work outside Claude Code need adding by hand.
