"""
Porta: ConfigurationStore.

Um plugin pode ler e escrever suas proprias configuracoes atraves
deste contrato. O Core injeta a implementacao no CoreAPI.

A implementacao concreta pode ser trocada (SQLite, Redis, arquivo)
sem que o plugin precise mudar uma linha.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ConfigurationStore(Protocol):
    """Armazenamento de configuracoes para plugins.

    Cada configuracao e identificada por (plugin_id, key).
    """

    def get(self, plugin_id: str, key: str, default: str = "") -> str:
        """Retorna o valor de uma configuracao.

        Args:
            plugin_id: Nome do plugin.
            key: Chave da configuracao.
            default: Valor padrao se a chave nao existir.

        Returns:
            Valor da configuracao ou default.
        """
        ...

    def set(self, plugin_id: str, key: str, value: str) -> None:
        """Define o valor de uma configuracao.

        Cria se nao existir, atualiza se ja existir.
        """
        ...

    def get_all(self, plugin_id: str) -> dict[str, str]:
        """Retorna todas as configuracoes de um plugin."""
        ...

    def delete(self, plugin_id: str, key: str) -> bool:
        """Remove uma configuracao. Retorna True se existia."""
        ...

    def clear(self, plugin_id: str) -> bool:
        """Remove todas as configuracoes de um plugin."""
        ...