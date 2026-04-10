---
name: thermal-conductivity-lab
description: Use when working on the Thermal-90, Raspberry Pi 5, infrared thermography, metal thermal conductivity experiment, .dat thermal data, ROI analysis, smart hot plate setup, experiment notes, or PINN inverse thermal conductivity workflow in C:\Users\28146\Desktop\thermal-conductivity-project.
---

# Thermal Conductivity Lab

## Overview

This is the entry skill for the Thermal-90 metal thermal conductivity project. Keep the project moving from the real current state: read project memory first, choose the right supporting skill, act in small verified steps, and update memory when the project changes.

## Start Every Task

1. Treat the workspace as `C:\Users\28146\Desktop\thermal-conductivity-project` unless the user says otherwise.
2. Read these before deciding:
   - `docs/agent_memory/current-state.md`
   - `docs/agent_memory/decisions.md`
   - `docs/agent_memory/next-actions.md`
3. If the task mentions an error, bug, failed command, capture problem, VNC issue, or unexpected data, also read:
   - `docs/agent_memory/bugs-and-fixes.md`
4. Do not restart from Raspberry Pi basics. Continue from the recorded experimental state.
5. Reply in Chinese by default unless the user asks otherwise.
6. Keep responses short and action-oriented. Give only the next small step unless a plan is explicitly requested.

## Skill Routing

| Situation | Required behavior |
| --- | --- |
| Bug, traceback, hardware capture failure, VNC/display issue | Use `systematic-debugging` before proposing a fix. |
| Behavior/design change, new analysis capability, experiment workflow design | Use `brainstorming` first, but keep questions small and tied to the current project state. |
| Code change in `code/` or `code_appendix/` | Use `test-driven-development` unless the user asks for a throwaway edit; verify with `verification-before-completion`. |
| PDF, DOCX, XLSX, PPTX work | Use the matching file skill. |
| New skill search, install, upgrade, or capability extension | Use `skillhub-preference`; use `find-skills` when searching installable skills. |
| GitHub PR, issue, CI, publish flow | Use the GitHub plugin skill that matches the task. |
| Experiment setup, purchases, sample layout, hot plate route | Give concrete steps, current-state summary, next recommendation, and risks. |
| PINN or inverse modeling | First confirm data readiness: stable sample ROI, time axis, pixel scale, boundary/initial condition notes. |

## Project Rules

- Preserve the working Thermal-90 acquisition and VNC visualization chain.
- `code/` and `code_appendix/` may be edited when needed, but acquisition changes must be small, reversible, and verified.
- The PDF appendix file named by the user is `code_appendix/thermal90_ir_temp.py`.
- Raspberry Pi username is recorded in project memory. Connection credentials may be used when the user has provided them in the session, but do not write plaintext passwords into tracked files.
- Prefer the smart hot plate route for the formal experiment; keep PTC + MOS as backup unless the user changes direction.
- Prefer metal wire / metal rod samples for the formal one-dimensional conduction route. Use metal strips only for thermal-image debugging or fallback checks.

## Memory Updates

Update project notes after any of these:

- stage progress in acquisition, VNC, analysis, experiment setup, or PINN prep
- key code change
- confirmed bug fix
- purchase decision
- experiment-route change
- formal data collection or analysis result that changes next steps

Write updates to the smallest useful set:

- `docs/agent_memory/current-state.md` for current status
- `docs/agent_memory/bugs-and-fixes.md` for symptom, cause, fix, verification
- `docs/agent_memory/decisions.md` for route or purchase decisions
- `docs/agent_memory/next-actions.md` for the next 3-5 actions
- `docs/06-experiment-log.md` for stage-level experiment history

Every stage update should include: current state, next recommendation, risks.

## GitHub Sync

When project files are changed, save the update with git automatically:

1. Verify the relevant output first.
2. Check `git status -sb`.
3. Stage only the files that belong to the current update unless the user explicitly asks for all changes.
4. Commit with a short Chinese message.
5. Push the current branch to GitHub.

If the working tree contains unrelated user edits, do not silently include them.

## Subagents

Use subagents only when the user explicitly allows delegation or the task asks for subagents/parallel work.

Good splits:

- one explorer checks acquisition code risks while another checks analysis code shape
- one explorer reviews experiment notes while another inspects data-processing outputs
- one worker edits analysis code while another worker updates disjoint documentation files

Avoid:

- assigning the same file to multiple workers
- delegating the immediate blocker when the main thread needs the answer next
- using subagents just for ceremony

Tell workers they are not alone in the codebase and must not revert unrelated edits.

## Common Mistakes

- Do not give generic thermal-conductivity theory when the user needs wiring, commands, layout, or code.
- Do not suggest rewriting the acquisition stack when a targeted fix will protect the existing chain.
- Do not forget to update memory after a real experimental or code milestone.
- Do not assume the latest `.dat` file, ROI, or frame rate; inspect or ask if the repository cannot reveal it.
- Do not write plaintext passwords into README, docs, skill files, or git history.
