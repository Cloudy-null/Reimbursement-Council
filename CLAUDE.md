# CLAUDE.md

## Project
- Name: Claims Council
- One line: Health insurance reimbursement claims that decide themselves when it is safe, ask the member to fix what is missing, and give a human reviewer one clear card when it is not.
- Owner: Abdulrahman Aljahdali (GitHub: Cloudy-null). I must be able to explain every part of this repo in an interview.
- Context: Solve for Bupa hackathon, November 2026. Day 5 demo. Not tied to Bupa systems.

## Read these first, every session
1. docs/superpowers/specs/2026-11-23-claims-council-design.md (what we are building and why)
2. docs/HANDOVER.md (where things stand)
3. docs/CONVENTIONS.md (code, data and config rules)
4. docs/DATA_MODEL.md (the shapes every stage passes around)
5. docs/DESIGN.md before any UI work
6. docs/EXPERIMENTS.md before touching any switch, weight or threshold

If code and these docs disagree, stop and write CHECK in HANDOVER. Do not silently pick one.

## How to work with me
- Use the Superpowers workflow for any new feature: brainstorm, then write a plan, then build with tests, then review. Show me the design and the plan and wait for my OK before writing code.
- Exception: Overnight mode (below).
- For tiny fixes (a typo, one line), skip the full workflow.
- Small steps. One feature or fix per session. Do not start extra work I did not ask for.
- If you are unsure about something, write CHECK: <question> in the handover doc and keep going with the safest choice. Do not guess silently.
- Test data, do not trust it. Every input from outside (files, APIs, model output, datasets) gets validated.

## Overnight mode
Used when I start a session with "overnight mode". The spec and the plan in docs/superpowers/plans/ are already approved.
- Build layer by layer in the order in the spec, section 9. Do not start a layer until the previous one passes its tests.
- Work on the branch build/overnight. Never commit to main directly.
- Commit after each passing task. Tag each finished layer: layer-1, layer-2, layer-3, layer-4.
- If something is blocked for more than 3 attempts, write CHECK in HANDOVER, take the safest smaller version, and move on.
- At the end, update HANDOVER and SESSION_LOG and stop. Do not merge to main. I review in the morning.

## Skills: which one for which job
Installed skills (see the install list at the bottom):
- superpowers:brainstorming before any new feature or change in behavior.
- superpowers:writing-plans to turn an approved design into a plan.
- superpowers:subagent-driven-development or superpowers:executing-plans to build a plan.
- superpowers:test-driven-development for every core function and every pipeline stage.
- superpowers:systematic-debugging for any failing test or wrong number. Find the cause before fixing.
- superpowers:verification-before-completion before saying anything is done. Run the commands, show the output.
- superpowers:requesting-code-review at the end of each layer.
- frontend-design for building any screen. Impeccable for critique and polish. Playwright for screenshots.

Project skills (in .claude/skills/):
- run-ablation: any time you measure the effect of a switch, weight or threshold.
- add-council-member: any time you add or change a council member.
- add-defect-type: any time you add a new kind of bad claim to the synthetic data.

If a job matches a skill, use the skill. If you think a new repeated job deserves a skill, write CHECK in HANDOVER with a one line proposal. Do not create skills without my OK.

## Code structure (software engineering style)
- Separate layers. Keep these apart and never mix them in one file:
  - config: settings and env vars only, loaded in one place
  - domain/core: business logic, pure functions where possible, no I/O
  - adapters/io: anything that talks to the outside (model APIs, DB, files, datasets)
  - entrypoints: CLI, API routes, jobs, UI. Thin. They call core, they do not hold logic.
- One responsibility per module. If a file passes about 300 lines, propose a split.
- Clear names over clever code. No abbreviations I would not understand.
- Type hints in Python, everywhere.
- No secrets in code. Use .env and keep .env.example updated.
- Dependencies pinned. Explain why before adding any new library.
- Logging, not print. Errors are handled where they can be handled and logged with context.
- Every weight, threshold, cost and switch lives in config/*.yaml. Never hardcode one. See docs/CONVENTIONS.md.

## Tests and quality
- Every core function gets unit tests. Every pipeline stage gets at least one data test.
- Run the linter, formatter, and tests before saying a task is done. Report the results.
- CI (GitHub Actions) runs lint and tests on every push.
- No number goes into docs, README or slides unless it came from the test harness. Write where it came from (command and commit).

## Git
- Small commits with clear messages: <type>: <what changed> (feat, fix, refactor, test, docs, chore).
- Never add Co-Authored-By, "Generated with Claude Code", or session links to commit messages or PR descriptions. Commits are authored by me only.
- Never commit raw data, samples, secrets, or large binaries.

## Documentation (keep these updated, always)
- README.md: what it is, why it exists, screenshot or demo link, how to run it in under 5 commands, architecture diagram.
- docs/HANDOVER.md: the single source of truth for a new engineer (or a new chat) picking this up. Sections 1 to 6 are rewritten to stay current. Section 7 (history) only grows. Update it at the end of EVERY session.
- docs/SESSION_LOG.md: append a dated entry each session: what was done, what broke, decisions made, what is next. Never edit old entries.
- docs/decisions/NNN-title.md: one short file per important technical decision (context, options, choice, trade-off). If a decision is replaced later, keep the old file and mark it "Superseded by NNN".
- docs/EXPERIMENTS.md: every ablation result, with the command and commit that produced it.

## Writing style for all docs and all UI text
- Plain simple English, student level. No corporate language.
- No emojis. No em dashes.
- Arabic UI text is plain Modern Standard Arabic, short sentences.

## Frontend and design (for any UI work)
- Use the frontend-design skill for building and the Impeccable skill for critique and polish.
- Never use the default AI look: no Inter-only typography, no purple gradients, no generic hero with three feature cards.
- docs/DESIGN.md is the single source for look and feel. Wait for my OK on it before building UI.
- Colors, fonts and spacing only from the tokens in one file (see DESIGN.md). Reuse components, do not restyle each page.
- After building, take screenshots (desktop and mobile, Arabic and English) with Playwright, compare against the references, run an Impeccable audit, and fix what looks off before saying it is done.

## Install list (inside Claude Code)
- Superpowers: /plugin install superpowers@claude-plugins-official
- frontend-design: /plugin marketplace add anthropics/claude-code then /plugin install frontend-design@claude-code-plugins
- Impeccable: npx skills add pbakaus/impeccable
- Playwright for screenshots
