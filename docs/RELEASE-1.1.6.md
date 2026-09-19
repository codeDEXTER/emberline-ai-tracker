# Emberline 1.1.6

This release turns the public Emberline repository into a clearer, more
usable starting point for people adopting shared memory and delivery tracking
across Claude Code and OpenAI Codex.

## Included

- Fixed the CI merge gate by synchronizing the workflow page stamp and release
  version checks.
- Added the [`docs/user-guide/`](user-guide/) with guides for the product model,
  warm-up and reheat, proposals and tracker views, host adoption, repository
  structure, and search discoverability.
- Kept operational root contracts and `.github/workflows/` in their required
  conventional locations, with the structure explained for new users.
- Preserved the public cleanup from 1.1.5: no tracked session snapshots or
  orphaned presentation pages.

## Verification

The release gate is:

```sh
bin/workflow-stamp --check
bin/version-check --check
bin/quiet --label merge-gate --jobs auto -- python3 -m unittest discover -s tests -q
```

The repository is released under Apache-2.0 for code and CC BY 4.0 for
documentation and visual assets. See [`LICENSE`](../LICENSE),
[`LICENSE-DOCS`](../LICENSE-DOCS), and [`NOTICE`](../NOTICE).
