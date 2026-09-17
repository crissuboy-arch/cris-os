# Tool Registry

Catálogo de ferramentas de **produção** de ativos que a Product Factory usa,
sem acoplar a Factory a nenhum fornecedor específico. Implementado em
`core/tool_registry.py`.

**Não confundir** com `tools/base.py:Tool` (as ferramentas dos *agentes* do
Telegram, ex.: `top_produtos_scalaflow`). Este registry é sobre ferramentas
de *produção* de ativos (gerar imagem, gerar vídeo, publicar site) — um
conceito novo da Fase 3.

## Princípio: não hardcodar fornecedor

A Product Factory pede uma **capability** (ex.: `COPY_GENERATOR`) e recebe
quem estiver registrado para ela. Hoje é o OpenRouter; amanhã pode ser
outra coisa, sem mudar o código da Factory.

```python
registry.executar(COPY_GENERATOR, blueprint=blueprint, llm=llm_economico)
```

## Capabilities registradas nesta fase

| Capability | Disponível? | Fornecedor | Observação |
|---|---|---|---|
| `COPY_GENERATOR` | **Sim** | OpenRouter (tier econômico) | Único executor real desta fase — prova o contrato ponta a ponta |
| `MINI_APP_BUILDER` | Não | — | A Cris já tem um criador próprio (prompt → mini-app); falta interface/API definida |
| `IMAGE_GENERATOR` | Não | — | Assets caros não gerados automaticamente nesta fase |
| `VIDEO_GENERATOR` | Não | — | Idem |
| `LANDING_PAGE_BUILDER` | Não | — | Fundação apenas |
| `CODE_GENERATOR` | Não | — | Fundação apenas |
| `DRIVE_STORAGE` | Não | — | Fundação apenas |
| `GITHUB` | Não | — | Fundação apenas |
| `VERCEL` | Não | — | Fundação apenas |

## Nunca crasha a Product Factory

```python
def executar(self, capability, **kwargs) -> str:
    entry = self._entries.get(capability)
    if not entry:
        return f"Capability '{capability}' nao esta registrada..."
    if not entry.disponivel or not entry.executor:
        return f"Capability '{capability}' registrada mas indisponivel ({entry.observacao})."
    try:
        return entry.executor(**kwargs)
    except Exception as exc:
        return f"Falha ao executar '{capability}': {exc}"
```

Uma capability desconhecida ou indisponível nunca lança exceção — devolve
uma mensagem clara. Testado em `tests/test_product_architect.py`.

## Como registrar uma nova capability (fase futura)

```python
registry.registrar(
    MINI_APP_BUILDER,
    provider_name="nome-do-fornecedor",
    disponivel=True,
    executor=minha_funcao_que_gera_o_mini_app,
    observacao="descricao curta",
)
```

Nenhuma mudança na Product Factory é necessária — ela já sabe checar
`registry.disponivel(capability)` antes de tentar usar.
