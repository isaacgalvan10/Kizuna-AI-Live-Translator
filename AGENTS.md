## Agent skills

### Issue tracker

Local markdown files in `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` at root + `docs/adr/`. See `docs/agents/domain.md`.

## Working With Matt Pocock's Skills

I use Matt Pocock's agent skills (`mattpocock/skills`) as part of my engineering workflow.

- **Discover and use relevant skills.** Before substantial work, check which installed skills are available and use the appropriate ones when they fit the task. Do not assume a skill is installed just because it exists in the repository.
- **Prefer the skill's intended workflow.** Use relevant skills for requirements clarification, domain modeling, specification, TDD, debugging, architecture, implementation, and code review rather than inventing a competing process.
- **Use the right level of process.** Small fixes should remain lightweight. Use more structured workflows for complex features, ambiguous requirements, significant architectural changes, and production-critical work.
- **Keep implementation moving.** Complete the requested task when requirements are sufficiently clear. Do not turn every change into a lengthy planning or questioning session.
- **Preserve my learning goals.** Explain the important engineering concepts and decisions behind the work in concise, accessible language. Avoid repeating the full contents of a skill or adding unnecessary commentary.
- **Treat skills as guidance, not unquestionable authority.** Apply engineering judgment and prioritize actual project requirements, security, correctness, and maintainability. Explain meaningful deviations from a skill's recommendations.
- **Verify outcomes independently.** A skill's completion is not proof that the code works. Inspect the changes and run relevant tests and checks.
- **Keep project knowledge consistent.** When a skill updates project documentation, domain models, specifications, decision records, or learning notes, ensure those documents reflect the actual implementation and current decisions.

### Workflow Selection

Use the following as a guide, not a mandatory sequence:

- Unclear requirements or important design choices: consider `grill-me` or `grill-with-docs`.
- A substantial feature: consider `to-spec`, `to-tickets`, and `implement`.
- A bug or regression: consider `diagnosing-bugs`.
- A feature where behavior needs careful verification: consider `tdd`.
- A significant architecture concern: consider `codebase-design` or `improve-codebase-architecture`.
- A meaningful implementation: consider `code-review`.
- A concept I do not understand: consider `teach` or `wait-what`.

Use only the skills actually available in the current environment. These are examples of when skills may be useful, not instructions to invoke every skill on every task.