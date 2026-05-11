# DO NOT EDIT FILES IN THIS DIRECTORY DIRECTLY

This `.windsurf/` folder is **deployed from a centralized template** in `PM_REVIEW` repo.
Every sync overwrites local edits.

## To modify workspace tooling

1. Edit source in `d:\DoAn2\VSmartwatch\PM_REVIEW\tooling\.windsurf-template\`
2. Run sync:
   ```pwsh
   & 'd:\DoAn2\VSmartwatch\PM_REVIEW\tooling\.windsurf-template\sync.ps1' -Repo <this-repo-name>
   ```
3. Commit on `chore/<desc>` branch in BOTH PM_REVIEW (template source) AND this repo (deployed copy)
4. Open PR for both

## What gets synced

- `rules/` — operating rules
- `skills/` — AI skill definitions
- `workflows/` — slash commands
- `hooks/` — pre-run security hooks
- `hooks.json` — hook config
- `topology.md` — cross-repo data flow
- `repo-context.md` — auto-generated repo metadata

## Anti-loop integration

- Bug fix-attempt log → `PM_REVIEW/BUGS/<REPO-PREFIX>-<NUM>.md`
- Architectural decisions → `PM_REVIEW/ADR/<NNN>-<title>.md`
- See rule `60-context-continuity.md` for details
