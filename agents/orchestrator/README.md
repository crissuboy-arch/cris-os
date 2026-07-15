# 🧭 Agente: Orquestrador

**Status:** 🟡 Parcial (roteamento por código na fase 1)

Coordena qual agente responde a cada mensagem.

- **Fase 1:** o roteamento real acontece em `core/router.py` e em
  `core/orchestrator.py` (sempre Secretária por padrão).
- **Fase 2:** este agente usará o modelo para classificar mensagens e
  encaminhar para o agente certo. Veja `SYSTEM.md`.

## Arquivos
- `SYSTEM.md` — instruções de classificação (fase futura).
- `README.md` — este arquivo.
