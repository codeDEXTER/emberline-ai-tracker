# Emberline 1.1.7

This is the CI follow-up release for the public Emberline AI tracker.

It advances the release boundary after 1.1.6 and keeps the GitHub Actions
runner aligned with the renderer tests by installing Pillow explicitly.
The complete user guide, repository-structure audit, and search-discoverability
guidance remain in [`docs/user-guide/`](user-guide/).

Verification:

```sh
bin/workflow-stamp --check
bin/version-check --check
bin/quiet --label merge-gate --jobs auto -- python3 -m unittest discover -s tests -q
```

The repository is released under Apache-2.0 for code and CC BY 4.0 for
documentation and visual assets. See [`LICENSE`](../LICENSE),
[`LICENSE-DOCS`](../LICENSE-DOCS), and [`NOTICE`](../NOTICE).
