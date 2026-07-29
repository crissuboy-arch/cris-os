"""
Repositories — camada de acesso a dados do CRIS OS.
Cada repositorio faz CRUD de uma entidade no SQLite.
"""

from repositories.conversa_repo import ConversaRepository
from repositories.preferencia_repo import PreferenciaRepository
from repositories.cliente_repo import ClienteRepository
from repositories.projeto_repo import ProjetoRepository
from repositories.tarefa_repo import TarefaRepository
from repositories.prompt_repo import PromptRepository
from repositories.config_repo import ConfigRepository
from repositories.log_repo import LogRepository
