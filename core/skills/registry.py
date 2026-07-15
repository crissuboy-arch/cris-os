"""
SkillRegistry — descobre, valida, versiona e lista as Skills.

Responsabilidade única (SRP):
  - descobrir Skills automaticamente em `skills/`;
  - carregar os manifests (`manifest.json`);
  - validar a estrutura (os 8 arquivos do template oficial);
  - listar as Skills disponíveis;
  - habilitar/desabilitar Skills;
  - controlar versões.

NÃO executa Skills (fase futura) e é **independente do PluginManager** — a camada
de Skills é paralela à de agentes e não toca Event Bus, Memory nem Orquestrador.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from core.registry import Registry, discover_manifests
from core.skills.skill import Skill, SkillStatus

logger = logging.getLogger(__name__)

# Os 8 arquivos que toda Skill deve ter (template oficial).
REQUIRED_FILES = (
    "SKILL.md",
    "manifest.json",
    "README.md",
    "rules.md",
    "examples.md",
    "tools.md",
    "tests.md",
    "version.json",
)


class SkillLoadError(Exception):
    """Executor de skill declarado mas inválido (arquivo/classe ausente ou fora do contrato)."""


def _cumpre_contrato(executor) -> bool:
    """True se o executor cumpre a porta SkillExecutor (name/version/execute)."""
    return (
        isinstance(getattr(executor, "name", None), str)
        and isinstance(getattr(executor, "version", None), str)
        and callable(getattr(executor, "execute", None))
    )


class SkillRegistry(Registry):
    """Catálogo de Skills com descoberta, validação, versão e on/off."""

    def __init__(self) -> None:
        super().__init__()
        self._executors: dict[tuple[str, str], object] = {}

    # ------------------------------------------------------------------
    # Descoberta
    # ------------------------------------------------------------------
    def discover(self, skills_dir: str | Path) -> "SkillRegistry":
        """Varre `skills/`, valida e registra cada Skill (ignora `_template`)."""
        skills_dir = Path(skills_dir)
        if not skills_dir.exists():
            logger.warning("Pasta de skills nao encontrada: %s", skills_dir)
            return self

        for folder, dados in discover_manifests(skills_dir):
            skill = self._build(folder, dados)
            self.register(skill)
            if not skill.valid:
                logger.warning("Skill '%s' invalida: %s", skill.name, "; ".join(skill.issues))

        logger.info("Skills descobertas: %s", ", ".join(self.names()) or "(nenhuma)")
        return self

    def _validate_structure(self, folder: Path) -> list[str]:
        """Retorna a lista de arquivos do template que estão faltando."""
        return [f"falta {f}" for f in REQUIRED_FILES if not (folder / f).exists()]

    def _build(self, folder: Path, dados: dict | None) -> Skill:
        issues = self._validate_structure(folder)
        if dados is None:
            return Skill(
                name=folder.name, title=folder.name, description="", version="0.0.0",
                status=SkillStatus.INVALID, enabled=False, category="", path=folder,
                valid=False, issues=["manifest invalido"],
            )

        for campo in ("name", "version"):
            if not dados.get(campo):
                issues.append(f"manifest sem '{campo}'")

        return Skill(
            name=dados.get("name", folder.name),
            title=dados.get("title", folder.name),
            description=dados.get("description", ""),
            version=dados.get("version", "0.0.0"),
            status=dados.get("status", SkillStatus.SCAFFOLD),
            enabled=bool(dados.get("enabled", False)),
            category=dados.get("category", ""),
            path=folder,
            agents=list(dados.get("agents", [])),
            tools=list(dados.get("tools", [])),
            valid=not issues,
            issues=issues,
            executor=dados.get("executor", ""),
            domain=dados.get("domain", ""),
            input_schema=dados.get("input_schema", {}) or {},
            keywords=list(dados.get("keywords", []) or []),
        )

    # ------------------------------------------------------------------
    # Consultas (get/all/names herdados de Registry)
    # ------------------------------------------------------------------
    def enabled(self) -> list[Skill]:
        """Skills válidas E habilitadas (as que poderiam ser executadas)."""
        return [s for s in self.all() if s.enabled and s.valid]

    def version_of(self, name: str) -> str | None:
        s = self.get(name)
        return s.version if s else None

    # ------------------------------------------------------------------
    # Ciclo de vida (em memória; o padrão vem do manifesto)
    # ------------------------------------------------------------------
    def enable(self, name: str) -> bool:
        s = self.get(name)
        if s and s.valid:
            s.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        s = self.get(name)
        if s:
            s.enabled = False
            return True
        return False

    # ------------------------------------------------------------------
    # Carregamento do executor (para um agente ou o Orquestrador rodar a skill)
    # ------------------------------------------------------------------
    def load_executor(self, name: str):
        """
        Carrega, valida e cacheia o executor da skill (cumpre a porta SkillExecutor).

        Devolve a instância (cacheada por nome@versão) pronta para
        `execute(payload, context)`, ou **None** se a skill não tiver executor
        declarado (ainda sem execução). Se o executor for **declarado mas inválido**
        (arquivo/classe ausente ou fora do contrato), levanta `SkillLoadError`.
        """
        s = self.get(name)
        if not s or not s.valid or not s.executor:
            return None  # sem executor declarado -> ainda sem execução

        chave = (s.name, s.version)
        if chave in self._executors:
            return self._executors[chave]

        executor = self._instanciar_executor(s)
        if not _cumpre_contrato(executor):
            raise SkillLoadError(
                f"Executor da skill '{name}' não cumpre o contrato SkillExecutor."
            )
        self._executors[chave] = executor
        return executor

    def _instanciar_executor(self, s):
        """Importa e instancia a classe do executor. Levanta SkillLoadError se quebrado."""
        modulo, _, classe = s.executor.partition(":")
        arquivo = s.path / f"{modulo}.py"
        if not classe or not arquivo.exists():
            raise SkillLoadError(f"Executor '{s.executor}' inválido (arquivo/classe) em '{s.name}'.")
        mod_name = f"crisskill_{s.name.replace('-', '_')}_{modulo}"
        spec = importlib.util.spec_from_file_location(mod_name, arquivo)
        if spec is None or spec.loader is None:
            raise SkillLoadError(f"Não consegui carregar o módulo da skill '{s.name}'.")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls = getattr(mod, classe, None)
        if cls is None:
            raise SkillLoadError(f"Classe '{classe}' não encontrada na skill '{s.name}'.")
        return cls()
