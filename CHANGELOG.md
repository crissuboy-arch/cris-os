# Changelog

## [v1.0] - 2026-07-15

### Integração NVIDIA AI
- Novo provedor `NVIDIAProvider` com dois modelos independentes
- Router NVIDIA 8B (`meta/llama-3.1-8b-instruct`) para roteamento rápido
- Geração NVIDIA 70B (`meta/llama-3.1-70b-instruct`) para respostas de alta qualidade
- Fallback automático para Ollama local quando NVIDIA está indisponível
- Autenticação via `NVIDIA_API_KEY` no `.env`

### Fast Path de Roteamento
- Saudações roteadas em **~0.1ms** sem chamar LLM (regex match)
- Respostas sim/não com contexto roteadas diretamente
- Comandos com keyword de agente ou skill roteados sem LLM
- Redução de latência: de ~42s (3 chamadas 70B) para ~15s (1 chamada 70B)

### Logging e Métricas
- Timing por etapa (memória, router, execução, composer)
- Modelo utilizado registrado em cada etapa (nvidia/router, nvidia/generation, ollama)
- StageTimer para medição de latência por fase

### Router LLM com Múltiplos Provedores
- Suporte a policy de roteamento por papel (routing vs generation)
- Cada papel pode usar um provedor/modelo diferente
- Provider name tracking para logging

### Histórico Reduzido do Router
- Configuração `ROUTER_CONTEXT_MESSAGES=3` para o IntentRouter usar apenas 3 mensagens de contexto
- Agentes continuam com contexto completo (`MEMORY_CONTEXT_MESSAGES=12`)

### Streaming (Infra Preparada)
- Método `chat_stream()` no NVIDIAProvider
- Streaming não integrado ao Telegram por ora (channel off-limits)

### Outras Mudanças
- `config/settings.py`: novas variáveis `NVIDIA_ROUTER_MODEL`, `NVIDIA_GENERATION_MODEL`, `ROUTER_CONTEXT_MESSAGES`
- `core/runtime.py`: composition root com dois provedores NVIDIA + Ollama
- `core/application/timer.py`: StageTimer utilitário de latência
- Testes (`test_intent_router.py`): ajuste de texto para keyword match
- Documentação: README.md expandido com setup NVIDIA e estrutura atualizada
