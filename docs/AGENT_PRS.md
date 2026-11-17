# Agent Guidelines — Pull Requests

Follow these rules whenever creating or updating Pull Requests.

## Template & Checklist

- Fill in [.github/pull_request_template.md](../.github/pull_request_template.md) completely.
- Re-check the linked spec's [Definition of Ready](DEFINITION_OF_READY.md) and complete the [Definition of Done](DEFINITION_OF_DONE.md) checklist.
- Mark non-applicable items `n/a` with a reason; never delete template items.

## Traceability, GitHub Linking & Formatting

- Link the spec (`Closes #…` if fully completed, otherwise `Part of #…`) via a closing keyword in the PR body so the PR appears under "Development" in the issue, and map every acceptance criterion to its evidence. A comment with a link list is at most a supplement.
- For stacked PRs (where base is not `main`), PRs do not appear under "Development": create a Sub-Issue under the parent issue for each part, point the PR to it via `Closes #<Sub-Issue>` (which takes effect once the base becomes `main`), and model the order via `blocked by`.
- Verify all links after creation via the GitHub API (`subIssues`, `closingIssuesReferences`) — never assume they succeeded. Honestly report to the user what is linked and what GitHub technically does not display.
- PR titles and descriptions follow [Conventional Commits](CONVENTIONAL_COMMITS.md), are in English, max 100 chars for the title, and contain **no references to AI tools or assistants**.

## Verification & Exceptions

- Reviewers verify each ticked item against the diff and CI; an unchecked applicable item blocks merge.
- List unverified hardware-dependent behavior under "Open verifications and follow-ups" with an assigned owner.
- Hotfixes may reduce DoR and defer tests, but require a post-mortem and a follow-up issue.
