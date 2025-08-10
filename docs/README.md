# Documentation Index

This directory contains all project documentation organized by category.

## Quick Reference
- **README.md** (root) - Quick start, installation, and basic usage
- **MASTER_TODO.md** (root) - Single source of truth for all tasks and status
- **ARCHITECTURE.md** (root) - Architecture overview and contracts

## Operational Documentation
- **[OPERATOR_RUNBOOK.md](operational/OPERATOR_RUNBOOK.md)** - Recovery, backup, and operational procedures
- **[RUN_BOOK.md](operational/RUN_BOOK.md)** - Day-to-day operational procedures
- **[PRODUCTION_READINESS_CHECKLIST.md](operational/PRODUCTION_READINESS_CHECKLIST.md)** - Production deployment checklist

## Strategy & Planning
- **[MONETIZATION_STRATEGY.md](strategy/MONETIZATION_STRATEGY.md)** - Revenue and monetization approach
- **[PURPOSE_SUMMARY.md](strategy/PURPOSE_SUMMARY.md)** - Project purpose and goals

## Technical Documentation
- **[VIDEO_ENCODING_OPTIMIZATIONS.md](technical/VIDEO_ENCODING_OPTIMIZATIONS.md)** - Video processing optimizations and settings

## Security & Compliance
- **[RED_TEAM_BRIEFING.md](security/RED_TEAM_BRIEFING.md)** - Security assessment briefing
- **[RED_TEAM_FILE_INVENTORY.md](security/RED_TEAM_FILE_INVENTORY.md)** - Security file inventory

## Archived Documentation
- **[archive/](archive/)** - Deprecated and historical documentation
  - `CURSOR_TODO_FULL.txt` - Superseded by MASTER_TODO.md
  - `CURSOR_TASKS_AFTER_PAUSE.txt` - Superseded by MASTER_TODO.md
  - `AUDIT_REPORT.md` - Historical audit report
  - `repo_audit_probable_spork_v2.md` - Historical repository audit

## Documentation Standards
- All active documentation should be updated in their respective locations
- Task status and acceptance criteria are maintained only in `MASTER_TODO.md`
- Configuration examples and schemas are in `conf/` directory
- Environment variables and secrets are documented in `.env.example`
