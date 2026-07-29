"""Exceções do sistema de Capabilities."""


class CapabilityError(Exception):
    """Erro base do sistema de capabilities."""
    def __init__(self, message: str, capability_name: str = "") -> None:
        self.capability_name = capability_name
        super().__init__(message)


class CapabilityNotFoundError(CapabilityError):
    """Nenhum provider encontrado para a capability solicitada."""
    def __init__(self, name: str, constraint: str | None = None) -> None:
        msg = f"Capability '{name}' não encontrada"
        if constraint:
            msg += f" com constraint '{constraint}'"
        self.constraint = constraint
        super().__init__(msg, name)


class CapabilityUnavailableError(CapabilityError):
    """Capability existe, mas nenhum provider está saudável."""
    def __init__(self, name: str, reason: str = "todos os providers estão indisponíveis") -> None:
        super().__init__(
            f"Capability '{name}' indisponível: {reason}", name
        )


class CapabilityConflictError(CapabilityError):
    """Conflito entre dois providers da mesma capability."""
    def __init__(self, name: str, plugin_a: str, plugin_b: str, reason: str) -> None:
        self.plugin_a = plugin_a
        self.plugin_b = plugin_b
        super().__init__(
            f"Conflito na capability '{name}' entre {plugin_a} e {plugin_b}: {reason}",
            name,
        )


class CapabilityTimeoutError(CapabilityError):
    """A execução da capability excedeu o timeout."""
    def __init__(self, name: str, timeout_ms: int) -> None:
        super().__init__(
            f"Capability '{name}' excedeu timeout de {timeout_ms}ms", name
        )


class CapabilityPermissionError(CapabilityError):
    """O caller não tem permissão para chamar esta capability."""
    def __init__(self, name: str, caller_plugin_id: str) -> None:
        self.caller_plugin_id = caller_plugin_id
        super().__init__(
            f"Plugin '{caller_plugin_id}' não tem permissão para chamar '{name}'",
            name,
        )


class InvalidVersionError(ValueError):
    """Versão semântica inválida."""
    def __init__(self, version: str) -> None:
        super().__init__(f"Versão inválida: '{version}'")
        self.version = version