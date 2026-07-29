"""
Registries: catálogo genérico + descoberta de manifests.

`Registry` é a base comum (nome -> objeto). `AgentRegistry`/`ToolRegistry` apenas
a especializam. `discover_manifests` é a varredura única usada por agentes e skills
para achar `*/manifest.json`. Mantêm o núcleo desacoplado: o Orquestrador pergunta
"quais agentes existem?" sem saber quem são nem de onde vieram.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Registry:
    """Catálogo genérico nome -> objeto (o objeto precisa ter `.name`)."""

    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def register(self, item) -> None:
        self._items[item.name] = item

    def unregister(self, name: str) -> None:
        """Remove um item pelo nome."""
        self._items.pop(name, None)

    def get(self, name: str):
        return self._items.get(name)

    def all(self) -> list:
        return list(self._items.values())

    def names(self) -> list[str]:
        return list(self._items.keys())


class AgentRegistry(Registry):
    """Catálogo dos agentes especialistas disponíveis."""


class ToolRegistry(Registry):
    """
    Catálogo de ferramentas (capacidades no mundo real).

    Vazio na Fase 1 — existe para que agentes e o runtime já tenham onde plugar
    Google Calendar, Drive, GitHub, n8n, etc. nas próximas fases.
    """


def discover_manifests(
    directory: str | Path, skip_prefixes: tuple[str, ...] = ("_", ".")
) -> list[tuple[Path, dict | None]]:
    """
    Varre `<directory>/*/manifest.json` (ordenado), pulando pastas cujo nome começa
    com `skip_prefixes` (ex.: `_template`, ocultas).

    Devolve `[(pasta, dados), ...]` — `dados` é o dict do manifesto, ou `None` se o
    manifesto for ilegível/JSON inválido (o chamador decide o que fazer).
    """
    resultado: list[tuple[Path, dict | None]] = []
    for manifest_path in sorted(Path(directory).glob("*/manifest.json")):
        folder = manifest_path.parent
        if folder.name.startswith(skip_prefixes):
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = None
        resultado.append((folder, data))
    return resultado
