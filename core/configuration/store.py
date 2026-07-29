"""
PluginConfigStore — implementacao concreta de ConfigurationStore.

Usa o ConfigRepository existente, com plugin_id como escopo.
Futuramente pode ser substituida por Redis, arquivo, etc.
"""

from __future__ import annotations

from repositories.config_repo import ConfigRepository


class PluginConfigStore:
    """Implementacao de ConfigurationStore sobre SQLite (ConfigRepository).

    Cada plugin tem seu proprio namespace de configuracoes.
    O plugin_id e usado como usuario_id no repositorio existente.
    """

    def __init__(self) -> None:
        self._repo = ConfigRepository()

    def get(self, plugin_id: str, key: str, default: str = "") -> str:
        return self._repo.obter(plugin_id, key, default)

    def set(self, plugin_id: str, key: str, value: str) -> None:
        self._repo.definir(plugin_id, key, value)

    def get_all(self, plugin_id: str) -> dict[str, str]:
        items = self._repo.listar_por_usuario(plugin_id)
        return {item["chave"]: item["valor"] for item in items}

    def delete(self, plugin_id: str, key: str) -> bool:
        conn = self._repo._conn()
        cur = conn.execute(
            "DELETE FROM configuracoes WHERE usuario_id=? AND chave=?",
            (plugin_id, key),
        )
        conn.commit()
        return cur.rowcount > 0

    def clear(self, plugin_id: str) -> bool:
        return self._repo.resetar(plugin_id)