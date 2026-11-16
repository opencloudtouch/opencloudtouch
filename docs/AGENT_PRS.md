# Agent Guidelines — Pull Requests

Follow these rules whenever creating or updating Pull Requests.

## Template & Checklist
- Fill in [.github/pull_request_template.md](../.github/pull_request_template.md) completely.
- Re-check the linked spec's [Definition of Ready](DEFINITION_OF_READY.md) and complete the [Definition of Done](DEFINITION_OF_DONE.md) checklist.
- Mark non-applicable items `n/a` with a reason; never delete template items.

## Traceability & Formatting
- Link the spec (`Closes #…` if fully completed, otherwise `Part of #…`) and map every acceptance criterion to its evidence.
- PR titles and descriptions follow [Conventional Commits](CONVENTIONAL_COMMITS.md), are in English, max 100 chars for the title, and contain **no references to AI tools or assistants**.

## Verification & Exceptions
- Reviewers verify each ticked item against the diff and CI; an unchecked applicable item blocks merge.
- List unverified hardware-dependent behavior under "Open verifications and follow-ups" with an assigned owner.
- Hotfixes may reduce DoR and defer tests, but require a post-mortem and a follow-up issue.
