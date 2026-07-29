"""Erros do Event Bus."""


class EventBusError(Exception):
    """Erro base do Event Bus."""


class SubscriptionNotFoundError(EventBusError):
    """Tentativa de remover assinatura inexistente."""


class EventLogError(EventBusError):
    """Erro no Event Log."""