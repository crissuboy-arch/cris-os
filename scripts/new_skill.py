"""
new_skill.py — scaffolder oficial de Skills do CRIS OS.

Cria uma nova Skill em `skills/<nome>/` a partir do template `skills/_template/`,
preenchendo os placeholders e o manifesto. Garante que **toda Skill segue
exatamente o template oficial** (os 8 arquivos).

Uso (linha de comando):
    python scripts/new_skill.py <nome> --title "Titulo" --description "..." --category cat

Uso (programático):
    from scripts.new_skill import create_skill
    create_skill("minha-skill", "Minha Skill", "Faz X.", "categoria")
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "skills" / "_template"


def create_skill(
    name: str,
    title: str,
    description: str,
    category: str,
    version: str = "0.1.0",
    agents: list[str] | None = None,
    tools: list[str] | None = None,
    overwrite: bool = True,
) -> Path:
    """Cria a Skill e devolve o caminho. Idempotente (overwrite por padrão)."""
    if not TEMPLATE_DIR.exists():
        raise FileNotFoundError(f"Template nao encontrado em {TEMPLATE_DIR}")

    dest = ROOT / "skills" / name
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Skill '{name}' ja existe em {dest}")
    dest.mkdir(parents=True, exist_ok=True)

    subs = {
        "{{NAME}}": name,
        "{{TITLE}}": title,
        "{{DESCRIPTION}}": description,
        "{{CATEGORY}}": category,
        "{{VERSION}}": version,
        "{{DATE}}": date.today().isoformat(),
    }

    for arquivo in sorted(TEMPLATE_DIR.iterdir()):
        if not arquivo.is_file():
            continue
        texto = arquivo.read_text(encoding="utf-8")
        for chave, valor in subs.items():
            texto = texto.replace(chave, valor)
        (dest / arquivo.name).write_text(texto, encoding="utf-8")

    # Ajusta o manifesto com agentes/tools declarados (mantendo a estrutura do template).
    manifest_path = dest / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["agents"] = agents or []
    data["tools"] = tools or []
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return dest


def main() -> int:
    p = argparse.ArgumentParser(description="Cria uma nova Skill do CRIS OS a partir do template.")
    p.add_argument("name", help="nome em kebab-case, ex.: minha-skill")
    p.add_argument("--title", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--category", default="geral")
    p.add_argument("--version", default="0.1.0")
    p.add_argument("--agents", nargs="*", default=[])
    p.add_argument("--tools", nargs="*", default=[])
    a = p.parse_args()
    dest = create_skill(a.name, a.title, a.description, a.category, a.version, a.agents, a.tools)
    print(f"OK - Skill criada em {dest.relative_to(ROOT)}")
    print("Edite SKILL.md, rules.md, examples.md e o manifest.json conforme necessario.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
