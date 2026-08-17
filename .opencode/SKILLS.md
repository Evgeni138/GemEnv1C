# Skills Catalog — 1C AI Development Kit

> Complete reference of all available skills organized by category.
> Version: 1.2.0 | Updated: 2026-03-05

## Installation

Copy `.claude/` directory to your 1C project root, then run `claude` in that directory.

```bash
cp -r /path/to/1c-ai-development-kit/.claude /your/project/
cd /your/project
claude
```

Skills are invoked via `/skill-name` or triggered automatically by keyword matching.

---

## Global Skills (11)

Infrastructure, API, testing, code review — work across all project types.

| Skill | Description |
|-------|-------------|
| `api-expert` | Design REST/GraphQL APIs and implement API security (auth, JWT, CORS, rate limiting) |
| `code-review` | Review code changes, diffs, and agent results for bugs, security, and scope |
| `docker-expert` | Docker, containers, compose, dockerfile operations |
| `playwright-skill` | Browser automation, E2E tests, UI testing with Playwright |
| `postgres-expert` | PostgreSQL schema design, query optimization, EXPLAIN ANALYZE |
| `powershell-windows` | PowerShell scripts and Windows automation |
| `python-patterns` | Python scripts for infrastructure, tooling, and automation |
| `security-audit` | Security audit, vulnerability scan, OWASP review |
| `testing-patterns` | Unit tests, TDD, test coverage across languages |
| `visual-explainer` | Generate HTML visual explanations of systems, diffs, plans |
| `workflow-automation` | CI/CD pipelines, automation scripts, orchestration workflows |

---

## 1C — Configuration (2)

| Skill | Description |
|-------|-------------|
| `cf-init` | Create a new empty 1C configuration from scratch |
| `cf-edit` | Edit configuration properties, add/remove objects from ChildObjects, configure roles |

---

## 1C — Metadata (3)

| Skill | Description |
|-------|-------------|
| `meta-compile` | Add/create configuration objects: catalog, document, register, enum, constant, module, processor, HTTP service |
| `meta-edit` | Add, remove or change attributes, table parts, dimensions, resources of existing configuration object |
| `meta-remove` | Remove/delete an object from 1C configuration |

---

## 1C — Database (9)

| Skill | Description |
|-------|-------------|
| `db-create` | Create a new 1C infobase |
| `db-list` | List available databases, manage .v8-project.json registry |
| `db-dump-cf` | Export configuration to CF file (backup) |
| `db-load-cf` | Load configuration from CF file |
| `db-dump-xml` | Export configuration to XML files for version control |
| `db-load-xml` | Load configuration from XML source files |
| `db-update` | Apply configuration to database (UpdateDBCfg) |
| `db-run` | Launch 1C Enterprise client for a database |
| `db-load-git` | Smart load of changes from Git repository |

---

## 1C — Extensions (4)

| Skill | Description |
|-------|-------------|
| `cfe-init` | Create a new configuration extension (CFE) |
| `cfe-borrow` | Borrow an object from configuration into extension (intercept method, modify form, add attribute) |
| `cfe-patch-method` | Intercept a method of borrowed object: insert code before, after, or instead of original |
| `cfe-diff` | Analyze extension composition: borrowed objects, interceptors, verify inserted patches |

---

## 1C — Forms (5)

| Skill | Description |
|-------|-------------|
| `form-compile` | Create a managed form from scratch using JSON element definition |
| `form-edit` | Incrementally add or modify elements, attributes, and commands in existing managed form |
| `form-add` | Add a managed form to an existing configuration object |
| `form-patterns` | Reference for managed form layout patterns: archetypes, conventions, advanced techniques |
| `form-remove` | Remove a form from a configuration object |

---

## 1C — EPF/ERF (2 expert skills)

> **Expert Skills:** `epf-expert` and `erf-expert` are consolidated skills covering multiple operations each.

| Skill | Operations Covered |
|-------|-------------------|
| `epf-expert` | EPF: init, build, dump, add-form, bsp-init, bsp-add-command, validate |
| `erf-expert` | ERF: init, build, dump, validate |

---

## 1C — MXL/Templates (1 expert skill)

> **Expert Skill:** `mxl-expert` covers all MXL template operations.

| Skill | Operations Covered |
|-------|-------------------|
| `mxl-expert` | MXL: compile (from JSON), decompile (to JSON), template-add, template-remove, validate |

---

## 1C — DCS/SKD (2)

| Skill | Description |
|-------|-------------|
| `skd-compile` | Generate DCS (data composition schema) from JSON DSL |
| `skd-edit` | Modify existing DCS: add fields, totals, filters, parameters, change query text |

---

## 1C — Subsystems/Roles (2 expert skills)

> **Expert Skills:** consolidated multi-operation skills.

| Skill | Operations Covered |
|-------|-------------------|
| `subsystem-expert` | Subsystem: compile, edit (composition), interface-edit, validate |
| `role-expert` | Role: create with permissions set, validate |

---

## 1C — Inspection & Validation (2)

| Skill | Description |
|-------|-------------|
| `inspect` | Analyze any 1C object structure: configuration, metadata, form, DCS, MXL, role, subsystem |
| `validate` | Explicit validation of any 1C object: CF, CFE, metadata, form, subsystem, interface, role |

---

## 1C — Web/Testing (8)

| Skill | Description |
|-------|-------------|
| `web-publish` | Publish database via portable Apache (generates vrd + httpd.conf) |
| `web-info` | Check web server status and list published databases |
| `web-stop` | Stop Apache web server |
| `web-unpublish` | Remove web publication for a database |
| `web-test` | Playwright automation of 1C web client (autonomous/interactive/piped modes) |
| `1c-web-session` | Manage 1C in browser: sessions, navigation, forms, catalogs, documents, test data |
| `1c-test-runner` | AI testing of business logic via 1c-ai-debug MCP (no external dependencies) |
| `playwright-test` | Scaffold UI test after deploy (package.json + spec.js with JSONL log) |

---

## 1C — Knowledge/Planning (12)

| Skill | Description |
|-------|-------------|
| `1c-help-mcp` | Search 1C platform documentation |
| `1c-query-opt` | Optimize 1C queries: temp tables, JOINs, virtual table params, DCS, indexes |
| `bsp-patterns` | Patterns for working with BSP/SSL subsystems |
| `1c-project-init` | Initialize/enrich 1C project with skills, docs, CLAUDE.md, MCP |
| `brainstorm` | Main entry: idea/task → design → autonomous execution (express/standard/full) |
| `write-plan` | Create tasks.md from design.md with atomic steps and verification criteria |
| `subagent-dev` | Execute tasks.md with parallel subagents (implementer + reviewer per task) |
| `openspec-proposal` | Create formal change specification (proposal.md, tasks.md, design.md) |
| `openspec-apply` | Implement approved OpenSpec change following tasks.md step by step |
| `openspec-archive` | Archive completed OpenSpec change and update specifications |
| `help-add` | Add built-in help to a 1C object |
| `img-grid` | Overlay numbered grid on image to determine column proportions for form layout |

---

## Session Management (3) — NEW in v1.2.0

| Skill | Trigger | Description |
|-------|---------|-------------|
| `session-save` | "save session", "сохрани сессию" | Save current session state to `session-notes.md` |
| `session-restore` | "restore session", "продолжай" | Restore session state from `session-notes.md` and auto-continue |
| `session-retro` | "retro", "ретроспектива", "итоги" | Quick retrospective: what worked, what didn't, lessons learned |

---

## Quick Reference

Common task combinations:

| Task | Skills to Use |
|------|--------------|
| Create new catalog with form | `meta-compile` → `form-compile` |
| Add printed form to document | `mxl-expert` (compile) → `mxl-expert` (template-add) |
| Create external processor with DCS report | `epf-expert` (init) → `skd-compile` → `epf-expert` (build) |
| Patch standard configuration | `cfe-init` → `cfe-borrow` → `cfe-patch-method` |
| Set up web access to database | `web-publish` → `web-info` → `1c-web-session` |
| Start new feature (complex) | `brainstorm` (→ `write-plan` → `subagent-dev`) |
| Formal change management | `openspec-proposal` → `openspec-apply` → `openspec-archive` |
| Review agent work | `code-review` |
| Context getting high | `session-save` → `/clear` → `session-restore` |
| Optimize slow query | `1c-query-opt` |
| Build EPF from scratch | `epf-expert` (init) → `form-compile` → `epf-expert` (build) |
| Check role permissions | `inspect` (role) → `role-expert` (if changes needed) |

---

## Notes

### Expert Skills

Some skills are consolidated experts covering multiple operations:
- `epf-expert` — all EPF operations: init, build, dump, add-form, bsp-init, bsp-add-command, validate
- `erf-expert` — all ERF operations: init, build, dump, validate
- `mxl-expert` — all MXL operations: compile, decompile, template-add, template-remove, validate
- `role-expert` — role creation and validation
- `subsystem-expert` — subsystem compile, edit, interface-edit, validate

When working with these object types, invoke the expert skill — it handles all sub-operations.

### MCP-First Rule

In initialized 1C projects, always use MCP tools before writing code:
- `1c-help` — check syntax before writing BSL
- `1c-ssl` — check BSP patterns before implementing
- `1c-templates` — search templates before writing from scratch
- `1c-syntax-checker` — validate after writing BSL

Run `/1c-project-init` to set up MCP tools for your project.
