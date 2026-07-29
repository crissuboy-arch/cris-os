"""
StudioVersionDiff — calcula diff entre versoes de um agente.

Compara dois AgentDefinition e retorna campos alterados,
adicions, removidos e modificados.
"""

from __future__ import annotations

from typing import Any


def compute_diff(old: dict, new: dict, path: str = "") -> list[dict]:
    """Computa diff recursivo entre dois dicts.

    Retorna lista de alteracoes:
    [{"path": "name", "type": "changed", "old": "...", "new": "..."},
     {"path": "bindings.0.keyword", "type": "changed", ...},
     {"path": "rules.2", "type": "added", "new": "..."},
     {"path": "restrictions.0", "type": "removed", "old": "..."}]
    """
    changes: list[dict] = []

    all_keys = set(list(old.keys()) + list(new.keys()))

    for key in sorted(all_keys):
        full_path = f"{path}.{key}" if path else key
        old_val = old.get(key)
        new_val = new.get(key)

        if old_val == new_val:
            continue

        if key not in old:
            changes.append({"path": full_path, "type": "added", "new": _summarize(new_val)})
        elif key not in new:
            changes.append({"path": full_path, "type": "removed", "old": _summarize(old_val)})
        elif isinstance(old_val, dict) and isinstance(new_val, dict):
            changes.extend(compute_diff(old_val, new_val, full_path))
        elif isinstance(old_val, list) and isinstance(new_val, list):
            changes.extend(_diff_lists(old_val, new_val, full_path))
        else:
            changes.append({
                "path": full_path,
                "type": "changed",
                "old": _summarize(old_val),
                "new": _summarize(new_val),
            })

    return changes


def _diff_lists(old: list, new: list, path: str) -> list[dict]:
    """Compara duas listas."""
    changes: list[dict] = []
    max_len = max(len(old), len(new))

    for i in range(max_len):
        full_path = f"{path}.{i}"
        if i >= len(old):
            changes.append({"path": full_path, "type": "added", "new": _summarize(new[i])})
        elif i >= len(new):
            changes.append({"path": full_path, "type": "removed", "old": _summarize(old[i])})
        elif old[i] != new[i]:
            if isinstance(old[i], dict) and isinstance(new[i], dict):
                changes.extend(compute_diff(old[i], new[i], full_path))
            else:
                changes.append({
                    "path": full_path,
                    "type": "changed",
                    "old": _summarize(old[i]),
                    "new": _summarize(new[i]),
                })

    return changes


def _summarize(value: Any) -> str:
    """Resumir valor para exibicao."""
    if value is None:
        return "null"
    if isinstance(value, str):
        return value[:100] + ("..." if len(value) > 100 else "")
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return f"[{len(value)} items]"
    if isinstance(value, dict):
        return f"{{{len(value)} keys}}"
    return str(value)[:100]


def format_diff(changes: list[dict]) -> str:
    """Formata diff como texto legivel."""
    if not changes:
        return "Nenhuma alteracao"

    lines: list[str] = []
    icons = {"added": "+", "removed": "-", "changed": "~"}

    for c in changes:
        icon = icons.get(c["type"], "?")
        path = c["path"]
        if c["type"] == "added":
            lines.append(f"  {icon} {path}: {c['new']}")
        elif c["type"] == "removed":
            lines.append(f"  {icon} {path}: {c['old']}")
        else:
            lines.append(f"  {icon} {path}: {c['old']} -> {c['new']}")

    return "\n".join(lines)
