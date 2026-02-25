# Project Rules

## Session Task Tracking

- At the start of every new session, create a new file in `tasks/` following the existing naming convention: `<next-number>-<short-slug>.md` (e.g. `6-json-schema-validation.md`).
- Throughout the session, record all user requests, decisions, and requirements in that file in a requirements-style format — capturing **what** was asked, **why**, and any clarifications.
- This file serves as a living record of the session's work and should be kept up to date as the conversation progresses.

## Diagrams

- Always use **Mermaid** syntax for diagrams in documentation (inside ` ```mermaid ` code blocks).
- Never use ASCII art diagrams. If you encounter existing ASCII diagrams, convert them to Mermaid.

## Commits

- Always use **semantic commit messages** following the [Conventional Commits](https://www.conventionalcommits.org/) format: `<type>(<optional scope>): <description>`.
- Common types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`.
- Keep the subject line concise (under 72 characters) and use the imperative mood (e.g., "add", not "added").

## Git Workflow

- **Never commit directly to `main`.** If the current branch is `main`, create a new feature branch first (e.g., `feat/short-description`, `fix/short-description`).
- After making changes: stage, commit, and push the branch to the remote.
- When creating a pull request, **auto-populate the PR description** from the commit history on the branch — include a summary of changes, the motivation/context, and any relevant details. Do not leave the PR body empty.
