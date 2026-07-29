"""
services — camada de servicos (managers) do CRIS OS.

Cada manager encapsula a logica de negocio de um dominio.
Usam repositories internamente e expoem API limpa.
"""

from services.memory_manager import MemoryManager
from services.project_manager import ProjectManager
from services.client_manager import ClientManager
from services.task_manager import TaskManager
from services.prompt_library import PromptLibrary
from services.config_manager import ConfigManager
from services.activity_logger import ActivityLogger
