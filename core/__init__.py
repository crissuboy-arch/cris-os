"""
Núcleo do CRIS OS.

Mantido propositalmente sem imports pesados para evitar dependências circulares.
Importe os módulos diretamente, por exemplo:

    from core.application import Orchestrator
    from core.events import InProcessEventBus
    from core.plugins import PluginManager
    from core.models import IncomingMessage
"""
