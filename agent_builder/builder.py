"""
AgentBuilder — facade para criar, editar, versionar, publicar e gerenciar agentes.

Usa apenas interfaces publicas do Core:
  - AgentRegistry (registrar/desregistrar agentes para execucao)
  - AgentRuntime (executar agentes para teste)
  - PluginLoader (resolver capabilities)
  - Contracts: Agent, AgentContext, Task, AgentResult
"""

from __future__ import annotations

import logging
import uuid
from copy import deepcopy
from typing import Any

from agent_builder.agent import DynamicAgent
from agent_builder.models import AgentConfig, AgentDefinition, AgentStatus, CapabilityBinding
from agent_builder.store import AgentStore

logger = logging.getLogger(__name__)


class AgentBuilder:
    """Facade completa do Agent Builder.

    Nao toca no Core — apenas consome interfaces publicas.
    """

    def __init__(
        self,
        store: AgentStore,
        agent_registry: Any,
        runtime: Any | None = None,
        plugin_loader: Any | None = None,
    ) -> None:
        """
        Args:
            store: AgentStore para persistencia.
            agent_registry: AgentRegistry do Core (para registrar/desregistrar).
            runtime: AgentRuntime (opcional, para testar agentes).
            plugin_loader: PluginLoader (opcional, necessario se runtime usa plugin_loader).
        """
        self._store = store
        self._registry = agent_registry
        self._runtime = runtime
        self._plugin_loader = plugin_loader

    # ==================================================================
    # CRUD
    # ==================================================================

    def create(
        self,
        name: str,
        description: str = "",
        bindings: list[CapabilityBinding] | None = None,
        config: AgentConfig | None = None,
        agent_id: str | None = None,
    ) -> AgentDefinition:
        """Cria um novo agente (status: draft).

        Args:
            name: Nome unico do agente.
            description: Descricao.
            bindings: Lista de CapabilityBinding.
            config: Configuracoes (default se nao informado).
            agent_id: ID opcional (autogerado se vazio).

        Returns:
            AgentDefinition criado.
        """
        aid = agent_id or self._generate_id(name)
        definition = AgentDefinition(
            agent_id=aid,
            name=name,
            version="1.0.0",
            description=description,
            status=AgentStatus.DRAFT,
            bindings=bindings or [],
            config=config or AgentConfig(),
        )
        self._store.save(definition)
        logger.info("Agente criado: %s (%s)", name, aid)
        return definition

    def get(self, agent_id: str) -> AgentDefinition | None:
        """Obtem um agente pelo ID."""
        return self._store.load(agent_id)

    def get_by_name(self, name: str) -> AgentDefinition | None:
        """Busca um agente pelo nome (unico entre os ativos)."""
        for defn in self._store.list_all():
            if defn.name == name:
                return defn
        return None

    def update(self, agent_id: str, **kwargs: Any) -> AgentDefinition | None:
        """Atualiza campos de um agente.

        Se o agente estiver publicado, a atualizacao incrementa a versao
        e volta para draft (novas edicoes precisam republicar).

        Args:
            agent_id: ID do agente.
            **kwargs: Campos a atualizar (name, description, bindings, config, metadata).

        Returns:
            AgentDefinition atualizado, ou None se nao encontrado.
        """
        defn = self._store.load(agent_id)
        if defn is None:
            return None

        # Se publicado, nova edicao = nova versao draft
        if defn.status == AgentStatus.PUBLISHED:
            defn.version = self._bump_version(defn.version)
            defn.status = AgentStatus.DRAFT
            defn.published_at = None

        for key, value in kwargs.items():
            if key == "bindings":
                defn.bindings = value
            elif key == "config" and isinstance(value, dict):
                for k, v in value.items():
                    setattr(defn.config, k, v)
            elif key == "config" and isinstance(value, AgentConfig):
                defn.config = value
            elif hasattr(defn, key):
                setattr(defn, key, value)

        defn.updated_at = _agora()
        self._store.save(defn)
        logger.info("Agente atualizado: %s v%s", defn.name, defn.version)
        return defn

    def delete(self, agent_id: str) -> bool:
        """Remove agente do store e desregistra se estiver ativo."""
        self._unregister_agent(agent_id)
        return self._store.delete(agent_id)

    def list(self, status: str | None = None) -> list[AgentDefinition]:
        """Lista agentes, opcionalmente filtrando por status."""
        all_agents = self._store.list_all()
        if status:
            return [a for a in all_agents if a.status == status]
        return all_agents

    # ==================================================================
    # Ciclo de vida: publicacao / desativacao
    # ==================================================================

    def publish(self, agent_id: str) -> AgentDefinition | None:
        """Publica um agente: cria snapshot versionado + registra no AgentRegistry.

        Returns:
            AgentDefinition publicado, ou None se nao encontrado.
        """
        defn = self._store.load(agent_id)
        if defn is None:
            return None

        # Cria snapshot versionado
        self._store.save_version_snapshot(defn)

        # Atualiza status
        defn.status = AgentStatus.PUBLISHED
        defn.published_at = _agora()
        defn.updated_at = _agora()
        self._store.save(defn)

        # Registra no AgentRegistry para execucao
        self._register_agent(defn)

        logger.info("Agente publicado: %s v%s", defn.name, defn.version)
        return defn

    def deactivate(self, agent_id: str) -> AgentDefinition | None:
        """Desativa um agente: remove do AgentRegistry, mantem no store."""
        defn = self._store.load(agent_id)
        if defn is None:
            return None

        self._unregister_agent(agent_id)

        defn.status = AgentStatus.DEACTIVATED if defn.status == AgentStatus.PUBLISHED else AgentStatus.DRAFT
        defn.updated_at = _agora()
        self._store.save(defn)
        logger.info("Agente desativado: %s", defn.name)
        return defn

    # ==================================================================
    # Duplicacao
    # ==================================================================

    def duplicate(self, agent_id: str, new_name: str | None = None) -> AgentDefinition | None:
        """Duplica um agente com novo ID e nome.

        O agente duplicado comeca como draft na versao 1.0.0.
        """
        defn = self._store.load(agent_id)
        if defn is None:
            return None

        new_id = self._generate_id(new_name or defn.name)
        dup = AgentDefinition(
            agent_id=new_id,
            name=new_name or f"{defn.name} (copia)",
            version="1.0.0",
            description=defn.description,
            status=AgentStatus.DRAFT,
            bindings=deepcopy(defn.bindings),
            config=deepcopy(defn.config),
            metadata=deepcopy(defn.metadata),
        )
        self._store.save(dup)
        logger.info("Agente duplicado: %s -> %s", agent_id, new_id)
        return dup

    # ==================================================================
    # Execucao (teste)
    # ==================================================================

    def test(self, agent_id: str, instruction: str, session: str = "test") -> Any:
        """Executa um agente via AgentRuntime para teste.

        Se o agente nao estiver registrado, registra temporariamente,
        executa e desregistra.

        Returns:
            AgentResult do runtime.
        """
        defn = self._store.load(agent_id)
        if defn is None:
            return type("ErrResult", (), {"success": False, "output": f"Agente {agent_id} nao encontrado"})()

        was_registered = self._registry.get(defn.name) is not None
        if not was_registered:
            self._register_agent(defn)

        try:
            if self._runtime is None:
                return type("ErrResult", (), {"success": False, "output": "AgentRuntime nao configurado"})()
            result = self._runtime.execute(defn.name, instruction, session=session, correlation_id=f"test-{agent_id}")
            return result
        finally:
            if not was_registered:
                self._unregister_agent(agent_id)

    # ==================================================================
    # Export / Import
    # ==================================================================

    def export(self, agent_id: str, target_dir: str) -> str:
        """Exporta agente como diretorio independente.

        Returns:
            Caminho do diretorio exportado.
        """
        return str(self._store.export_to(agent_id, target_dir))

    def import_agent(self, source_dir: str) -> AgentDefinition | None:
        """Importa um agente de um diretorio.

        Carrega o manifest, registra no store.
        Se ja existir com mesmo agent_id, substitui.

        Returns:
            AgentDefinition importado.
        """
        agent_id = self._store.import_from(source_dir)
        defn = self._store.load(agent_id)
        logger.info("Agente importado: %s", defn.name if defn else agent_id)
        return defn

    # ==================================================================
    # Versionamento
    # ==================================================================

    def list_versions(self, agent_id: str) -> list[str]:
        """Lista versoes publicadas de um agente."""
        return self._store.list_versions(agent_id)

    def get_version(self, agent_id: str, version: str) -> AgentDefinition | None:
        """Carrega uma versao especifica."""
        return self._store.load_version(agent_id, version)

    # ==================================================================
    # Internos
    # ==================================================================

    def _register_agent(self, defn: AgentDefinition) -> None:
        """Cria DynamicAgent e registra no AgentRegistry."""
        dynamic = DynamicAgent(defn)
        try:
            self._registry.register(dynamic)
            logger.info("Agente registrado no AgentRegistry: %s", defn.name)
        except Exception as exc:
            logger.error("Falha ao registrar agente '%s': %s", defn.name, exc)

    def unregister_agent(self, agent_id: str) -> None:
        """Remove do AgentRegistry (pelo nome, se registrado com este ID).

        Metodo publico para uso externo (ex.: Studio routes).
        """
        self._unregister_agent(agent_id)

    def _unregister_agent(self, agent_id: str) -> None:
        """Remove do AgentRegistry (pelo nome, se registrado com este ID)."""
        defn = self._store.load(agent_id)
        if defn is None:
            return
        registered = self._registry.get(defn.name)
        if registered is not None:
            self._registry.unregister(defn.name)
            logger.info("Agente desregistrado do AgentRegistry: %s", defn.name)

    def get_registry(self) -> Any:
        """Retorna o AgentRegistry (metodo publico para uso externo)."""
        return self._registry

    @staticmethod
    def _generate_id(name: str) -> str:
        """Gera um ID unico a partir do nome."""
        suffix = uuid.uuid4().hex[:8]
        safe_name = "".join(c for c in name.lower() if c.isalnum() or c in "-_").strip("-_") or "agent"
        return f"{safe_name}-{suffix}"

    @staticmethod
    def _bump_version(current: str) -> str:
        """Incrementa o patch da versao semver."""
        parts = current.split(".")
        if len(parts) != 3:
            return "1.0.0"
        major, minor, patch = parts
        return f"{major}.{minor}.{int(patch) + 1}"


def _agora() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()