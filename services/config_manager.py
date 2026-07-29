"""
ConfigManager — gerenciador de configuracoes do CRIS OS.

Salva modelo padrao, temperatura, idioma, agente padrao, etc.
"""

import logging

from repositories.config_repo import ConfigRepository

logger = logging.getLogger(__name__)

# Valores padrao
DEFAULT_CONFIG: dict[str, str] = {
    "modelo_padrao": "",
    "temperatura": "0.7",
    "idioma": "pt-BR",
    "agente_padrao": "auto",
    "memoria_ativa": "true",
}


class ConfigManager:
    """Gerenciador de configuracoes do usuario."""

    def __init__(self) -> None:
        self.repo = ConfigRepository()

    def get(self, usuario_id: str, chave: str) -> str:
        """Retorna uma configuracao (com fallback ao padrao)."""
        valor = self.repo.obter(usuario_id, chave)
        if valor:
            return valor
        return DEFAULT_CONFIG.get(chave, "")

    def set(self, usuario_id: str, chave: str, valor: str) -> int:
        """Define uma configuracao."""
        return self.repo.definir(usuario_id, chave, valor)

    def listar(self, usuario_id: str) -> dict[str, str]:
        """Retorna todas as configuracoes do usuario (mesclado com defaults)."""
        salvas = self.repo.listar_por_usuario(usuario_id)
        resultado = dict(DEFAULT_CONFIG)
        for item in salvas:
            resultado[item["chave"]] = item["valor"]
        return resultado

    def resetar(self, usuario_id: str) -> bool:
        """Reseta todas as configuracoes para o padrao."""
        return self.repo.resetar(usuario_id)
