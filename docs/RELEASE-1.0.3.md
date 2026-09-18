# common-rules 1.0.3

Patch release for the shared tracker renderer.

## Included

- Responsive expanded-tree rows with stable, non-wrapping item IDs.
- Wrapping `next:` guidance and long item titles without horizontal clipping.
- A narrow-pane flex fallback for browser views used by Claude Code and Codex.

## Verification

The PhotoVault app tracker was regenerated from the shared renderer and checked
with P70 expanded in the live browser. IDs remain intact and long row content
wraps within the tracker surface.
