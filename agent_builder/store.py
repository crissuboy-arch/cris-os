"""
Store — persistencia em arquivos JSON para definicoes de agentes.

Cada agente e um diretorio independente:
    agent_builder/agents/<agent_id>/
        manifest.json       # definicao atual (sempre a mais recente)
        history/
            v1.0.0.json     # snapshots de versoes publicadas
            v1.1.0.json

Isso torna export/import uma copia de diretorio.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from agent_builder.models import AgentDefinition

logger = logging.getLogger(__name__)


class AgentStore:
    """Armazenamento de agentes como artefatos independentes em disco."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # CRUD basico
    # ------------------------------------------------------------------

    def save(self, definition: AgentDefinition) -> None:
        """Salva ou atualiza o manifest de um agente."""
        agent_dir = self._agent_dir(definition.agent_id)
        agent_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = agent_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(definition.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug("Agente salvo: %s v%s", definition.name, definition.version)

    def load(self, agent_id: str) -> AgentDefinition | None:
        """Carrega um agente pelo ID."""
        manifest_path = self._manifest_path(agent_id)
        if not manifest_path.exists():
            return None
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return AgentDefinition.from_dict(data)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("Manifest invalido para '%s': %s", agent_id, exc)
            return None

    def delete(self, agent_id: str) -> bool:
        """Remove o diretorio do agente. Retorna True se existia."""
        agent_dir = self._agent_dir(agent_id)
        if not agent_dir.exists():
            return False
        shutil.rmtree(agent_dir)
        logger.info("Agente removido: %s", agent_id)
        return True

    def list_ids(self) -> list[str]:
        """Lista todos os IDs de agentes armazenados."""
        if not self._base.exists():
            return []
        return sorted(
            d.name for d in self._base.iterdir()
            if d.is_dir() and (d / "manifest.json").exists()
        )

    def list_all(self) -> list[AgentDefinition]:
        """Carrega todos os agentes."""
        result: list[AgentDefinition] = []
        for agent_id in self.list_ids():
            defn = self.load(agent_id)
            if defn is not None:
                result.append(defn)
        return result

    def exists(self, agent_id: str) -> bool:
        return self._manifest_path(agent_id).exists()

    # ------------------------------------------------------------------
    # Versionamento
    # ------------------------------------------------------------------

    def save_version_snapshot(self, definition: AgentDefinition) -> Path:
        """Salva uma copia versionada em history/v<version>.json.

        Retorna o caminho do snapshot.
        """
        agent_dir = self._agent_dir(definition.agent_id)
        history_dir = agent_dir / "history"
        history_dir.mkdir(parents=True, exist_ok=True)

        version_path = history_dir / f"v{definition.version}.json"
        version_path.write_text(
            json.dumps(definition.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Snapshot versionado: %s v%s", definition.name, definition.version)
        return version_path

    def list_versions(self, agent_id: str) -> list[str]:
        """Lista as versoes disponiveis no historico."""
        history_dir = self._agent_dir(agent_id) / "history"
        if not history_dir.exists():
            return []
        versions: list[str] = []
        for f in sorted(history_dir.glob("v*.json")):
            ver = f.stem.lstrip("v")
            versions.append(ver)
        return versions

    def load_version(self, agent_id: str, version: str) -> AgentDefinition | None:
        """Carrega uma versao especifica do historico."""
        version_path = self._agent_dir(agent_id) / "history" / f"v{version}.json"
        if not version_path.exists():
            return None
        try:
            data = json.loads(version_path.read_text(encoding="utf-8"))
            return AgentDefinition.from_dict(data)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("Snapshot invalido para '%s' v%s: %s", agent_id, version, exc)
            return None

    # ------------------------------------------------------------------
    # Export / Import
    # ------------------------------------------------------------------

    def export_to(self, agent_id: str, target_dir: str | Path) -> Path:
        """Copia o diretorio do agente para target_dir.

        Retorna o caminho do diretorio copiado (target_dir / <agent_id>).
        """
        source = self._agent_dir(agent_id)
        if not source.exists():
            raise FileNotFoundError(f"Agente {agent_id} nao encontrado em {source}")
        target = Path(target_dir) / agent_id
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        logger.info("Agente exportado: %s -> %s", agent_id, target)
        return target

    def import_from(self, source_dir: str | Path) -> str:
        """Importa um agente de source_dir para o store.

        source_dir deve conter manifest.json.
        Retorna o agent_id importado.
        """
        source = Path(source_dir)
        manifest_path = source / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Diretorio sem manifest.json: {source}")

        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        agent_id = data.get("agent_id", source.name)

        # Se ja existe, faz merge preservando o existente
        target = self._agent_dir(agent_id)
        if target.exists():
            logger.warning("Agente '%s' ja existe — substituindo", agent_id)
            shutil.rmtree(target)
        shutil.copytree(source, target)
        logger.info("Agente importado: %s <- %s", agent_id, source)
        return agent_id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _agent_dir(self, agent_id: str) -> Path:
        return self._base / agent_id

    def _manifest_path(self, agent_id: str) -> Path:
        return self._agent_dir(agent_id) / "manifest.json"