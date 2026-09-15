"""What an item is worth once the project's defaults apply (proposal 25, Z-03).

  effective_value(item, value_defaults) -> (value | None, source)

An item's own `value` wins; otherwise its `cluster`'s entry in the project's
`value_defaults` (.common-rules.json); otherwise None, "unsized" -- never a
guess, because a guessed value would move the item's lane.
"""
from __future__ import annotations


def effective_value(item: dict, value_defaults: dict) -> tuple[str | None, str]:
    if item.get("value") is not None:
        return item["value"], "item"
    cluster = item.get("cluster")
    if cluster is not None and cluster in (value_defaults or {}):
        return value_defaults[cluster], f"default for {cluster}"
    return None, "unsized"
