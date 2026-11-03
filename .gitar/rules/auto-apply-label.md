---
title: "Enable auto-apply"
description: "Turn on Gitar auto-apply for every pull request through the gitar-managed label"
type: automation
when: "A pull request is opened"
actions: "Add the label gitar-managed"
---

# Enable auto-apply

Gitar's auto-apply preference lasts only for the life of one pull request and has no dashboard default.
The label `gitar-managed` enables auto-apply for a pull request, so every new pull request gets that label.

- Add the label `gitar-managed` when the pull request is opened. Do not add or remove any other label.
- Which review findings may be applied automatically is limited by the organization criteria and by `.gitar/config/apply.md`.
- Never touch labels starting with `phase:`, `wait:` or `resolution:`; they belong to `oct-status`.
