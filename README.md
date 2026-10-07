# Timesheet

A Claude Code plugin that keeps a daily work log from your Claude Code chat history and turns it into a weekly timesheet: hours per project per day, plus a short description of what you did.

Everything stays on your Mac. The plugin reads your local chat history and git commits, and writes Markdown files to your work log folder.

## Install

You need an up-to-date Claude Code. No GitHub account is needed.

```bash
claude plugin marketplace add YorJor/timesheet
```

```bash
claude plugin install timesheet@timesheet
```

Then open a new chat in the Claude desktop app's Code tab and run:

```
/timesheet:timesheet setup
```

Setup does four things:
1. Creates your work log folder (default `~/Documents/worklog`).
2. Keeps chat history for at least 40 days, so a weekly timesheet never misses days.
3. Adds a **Daily work log** task that runs every evening at 18:30 and logs the day.
4. Fills in the log for the past two weeks.

After setup, click **Run now** once on Daily work log in the Scheduled section of the sidebar, so the task's tool approvals are saved for the evening runs.

## Use

| Command | What it does |
|---|---|
| `/timesheet:timesheet` | This week's timesheet, Monday to today |
| `/timesheet:timesheet last week` | Last week's timesheet |
| `/timesheet:timesheet 2026-10-01..2026-10-15` | Any date range |
| `/timesheet:timesheet log` | Update the work log now (the evening task does this for you) |

You can also just ask: "what did I work on this week?"

### What you get

The work log has one file per month, `YYYY-MM.md`, with a section per day:

| Project | Hours | What I did |
|---|---:|---|
| Billing | 4.25 | Built the invoice export and fixed rounding in tax totals |

Weekly timesheets are saved to `timesheets/YYYY-Www.md` in the same folder.

## How hours are counted

Hours are the time Claude Code was active in each project folder. Messages less than 15 minutes apart count as one block of work, and parallel chats in the same project are counted once. Hours are rounded to the quarter hour.

Meetings and work done outside Claude Code don't show up, so treat the hours as a starting point and add the rest yourself.

A project is the folder the chat was started in. Chats started without a project folder show up as **No project folder**.

## Settings

| Setting | Default | |
|---|---|---|
| Work log folder | `~/Documents/worklog` | Change it in `/config` → Timesheet, or with `claude plugin configure timesheet@timesheet` |

## Update

```bash
claude plugin marketplace update timesheet
```

```bash
claude plugin update timesheet@timesheet
```

Then open a new chat.

## Notes

- The evening task needs the Claude desktop app. It runs only while the app is open; if the app was closed at 18:30, the task runs the next time you open it and catches up on missed days.
- In the terminal, `/timesheet:timesheet` still works, but only for the days still in your chat history (40 days after setup).
- Commits are matched to your global git email (`git config --global user.email`).
