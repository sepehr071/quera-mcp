<!-- mcp-name: io.github.sepehr071/quera-mcp -->

# quera-mcp: Quera (کوئرا) jobs, contests, problems and courses MCP server for AI agents

**quera-mcp is an unofficial, read-only MCP server that gives AI agents the public data of Quera (quera.org), the Iranian developer platform.**
Its 9 tools search tech jobs and companies (Magnet), list programming contests, search and read problems from the public problemset, and browse the College course catalog.
No API key or Quera account is needed. It works in Claude, Cursor, Copilot and any other MCP client.

[![PyPI](https://img.shields.io/pypi/v/quera-mcp?color=2563eb)](https://pypi.org/project/quera-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/quera-mcp)](https://pypi.org/project/quera-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](https://github.com/sepehr071/quera-mcp/blob/main/LICENSE)

[For AI agents](#for-ai-agents) · [Quick start](#quick-start) · [What it can do](#what-it-can-do) · [Tools](#tools) · [FAQ](#faq) · [فارسی](#فارسی)

---

## For AI agents

- **What:** unofficial MCP server (model context protocol) for quera.org: tech job search with filters (keyword, level, remote, city, tech stack, job type, company, sort), full job postings, company search and profiles, running/upcoming/past programming contests, problem search and statements, and the College course catalog with prices.
- **Install:** `uvx quera-mcp` or `claude mcp add quera -- uvx quera-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none, no API key or account. Optional `QUERA_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored.
- **Access:** read-only. It cannot log in, apply to jobs, submit solutions or register for anything, so no confirmation is needed before calling any tool.
- **Tools:** 14, all prefixed `qr_`. Typical sequences: `qr_jobs` -> `qr_job` -> `qr_company`; `qr_companies` -> `qr_company`; `qr_problem_filters` -> `qr_problems` -> `qr_problem`; `qr_contests` -> `qr_event`; `qr_courses`; `qr_bootcamps`; `qr_blog`; `qr_salaries`.
- **Use when:** the user asks about developer jobs in Iran (Tehran, remote, junior, Python...), which companies hire, programming contests, practice problems, or Quera course options and prices.
- **Do not use when:** the user wants other job boards, personal Quera data (profiles, submissions, rankings) or to apply or submit anything.
- **Output:** compact JSON. Salaries are Toman per month when the employer published them; contest times are UTC. Text is Persian or English as the author wrote it.

## What it can do

- **Search jobs** on Quera Magnet with the site's own filters: keyword, seniority (intern to lead), remote, city, tech stack, full/part-time/project, company, industry, sorting by newest, trending or salary
- **Read a job** in full: description, requirements, benefits, skills, salary, deadline and related jobs
- **Search companies** (3,000+) by name, city, size, industry and tech stack, and read a profile with its open jobs
- **List contests**: what is running or upcoming, the latest finished ones, and an archive per topic and organizer
- **Search problems** among about 2,000 public problems by name, topic, difficulty and source, and read the statement
- **Browse College courses** by learning path, level and keyword, with list prices

Example prompts:

- "Remote junior Python jobs on Quera, newest first."
- "Which companies in Isfahan are hiring backend developers?"
- "Show the open jobs and tech stack of Kaya."
- "Is there a Quera contest coming up? Which ones did Digikala organize?"
- "Easy practice problems about data structures."
- "Which Quera course teaches Django and how much is it?"
- <span dir="rtl">آگهی‌های استخدام دورکاری برنامه‌نویس پایتون در کوئرا را نشان بده.</span>

## Quick start

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). No API key or account.

```bash
claude mcp add quera -- uvx quera-mcp
```

Claude Desktop, Cursor and other clients:

```json
{
  "mcpServers": {
    "quera": { "command": "uvx", "args": ["quera-mcp"] }
  }
}
```

## Tools

| Tool | What it does |
|---|---|
| `qr_jobs` | Search open tech jobs (15 per page) with filters |
| `qr_job` | One posting in full |
| `qr_job_filters` | Cities, industries, company sizes and popular tech codes the filters accept |
| `qr_companies` | Search company profiles |
| `qr_company` | A company profile and its open jobs |
| `qr_contests` | Running, upcoming and finished contests, or the archive of one topic |
| `qr_problems` | Search the public problemset |
| `qr_problem` | One problem statement with stats |
| `qr_courses` | College course catalog with prices |
| `qr_salaries` | Published salaries in open jobs, summarized by seniority level |
| `qr_problem_filters` | Topic slugs and contest ids `qr_problems` accepts |
| `qr_event` | An event page (CodeCup, hackathon): schedule, prizes, sub-events |
| `qr_bootcamps` | Bootcamps open for registration with price and seats, or one in full (syllabus, instructors) |
| `qr_blog` | Search or read the Quera blog |

## FAQ

**Does it need a Quera account?** No. It reads the same public pages anyone sees.

**Is it official?** No. It is an independent project and is not affiliated with Quera.

**Where does it work?** Quera answers both inside and outside Iran. Set `QUERA_MCP_PROXY` if your network blocks it.

**Why are there so few jobs?** Quera Magnet is a small curated board (tens of open postings); the site's own filters decide what is listed.

## فارسی

`quera-mcp` یک سرور MCP غیررسمی و فقط‌خواندنی برای کوئرا (quera.org) است: جستجوی آگهی‌های استخدام و شرکت‌ها، مسابقات برنامه‌نویسی، مسئله‌های بانک سؤال و دوره‌های کالج کوئرا. نیازی به حساب یا کلید API نیست.

نصب: `claude mcp add quera -- uvx quera-mcp`

## License

MIT. Author: Sepehr Radmard (سپهر رادمرد), [github.com/sepehr071](https://github.com/sepehr071), [linkedin.com/in/sepehr-radmard](https://linkedin.com/in/sepehr-radmard).
