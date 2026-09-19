# Emberline 1.1.8

This patch synchronizes the literal release-version regression test with the
published version contract. It keeps the CI gate honest while retaining the
public Emberline user guide, repository-structure audit, and discoverability
guidance.

Verification:

```sh
bin/workflow-stamp --check
bin/version-check --check
bin/quiet --label merge-gate --jobs auto -- python3 -m unittest discover -s tests -q
```

The repository is released under Apache-2.0 for code and CC BY 4.0 for
documentation and visual assets. See [`LICENSE`](../LICENSE),
[`LICENSE-DOCS`](../LICENSE-DOCS), and [`NOTICE`](../NOTICE).
