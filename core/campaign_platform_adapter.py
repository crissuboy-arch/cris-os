"""
CampaignPlatformAdapter -- contrato/porta abstrata para futuros conectores
externos de execucao de campanha (Meta/Google/TikTok Ads).

Fase 6: SOMENTE o contrato existe. NENHUMA implementacao concreta conecta a
nenhuma API externa -- nao ha `MetaAdsAdapter`/`GoogleAdsAdapter`/
`TikTokAdsAdapter` nesta fase, nem import de nenhum SDK de Ads. As operacoes
mutaveis (`create_campaign`/`pause_campaign`/`update_budget`) ficam
EXPLICITAMENTE desabilitadas na classe base (levantam
`ExternalExecutionDisabledError`), independente de qual subclasse futura as
herde -- uma subclasse teria que sobrescrever o metodo de proposito para
burlar isso, o que nao acontece nesta fase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ExternalExecutionDisabledError(Exception):
    """Levantada por qualquer tentativa de mutacao externa nesta fase --
    nunca deve ser capturada e "contornada": existe para deixar uma
    execucao real IMPOSSIVEL de acontecer por acidente, nao so improvavel."""


class CampaignPlatformAdapter(ABC):
    """
    Porta abstrata -- uma implementacao concreta futura (ex.:
    `MetaAdsAdapter`) faria a ponte real com uma API de Ads especifica.
    NENHUMA implementacao concreta existe nesta fase.
    """

    @abstractmethod
    def validate(self, campaign_spec) -> list[str]:
        """Lista de problemas de validacao (vazia = valido). Operacao de
        LEITURA -- nunca muta nada externamente."""

    @abstractmethod
    def preview(self, campaign_spec) -> dict:
        """Pre-visualizacao estruturada da campanha. Operacao de LEITURA --
        nunca muta nada externamente."""

    def create_campaign(self, campaign_spec):
        raise ExternalExecutionDisabledError(
            "Criacao de campanha externa esta DESABILITADA nesta fase -- "
            "nenhuma API de Ads e chamada.",
        )

    def pause_campaign(self, campaign_id: str):
        raise ExternalExecutionDisabledError(
            "Pausar campanha externa esta DESABILITADO nesta fase.",
        )

    def update_budget(self, campaign_id: str, budget: dict):
        raise ExternalExecutionDisabledError(
            "Alterar orcamento externo esta DESABILITADO nesta fase.",
        )

    @abstractmethod
    def fetch_metrics(self, campaign_id: str) -> dict:
        """Buscaria metricas REAIS de uma campanha ja publicada. Operacao de
        LEITURA -- nenhuma implementacao concreta existe nesta fase (sem
        conector real conectado)."""
