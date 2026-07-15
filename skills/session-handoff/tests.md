# Testes — Session Handoff

## Critérios de aceite
- [x] `save` grava um item `type="handoff"` recuperável na memória permanente (L3).
- [x] `resume` reconstrói o **último** pacote da **mesma sessão** (e informa quando não há).
- [x] `save` e `resume` registram evento no **Event Log**.
- [x] Acionável por **qualquer agente** e pelo **Orquestrador** (via `SkillContext`).
- [x] Nenhuma ação externa (só leitura/escrita local).

## Testes automatizados
Arquivo: [`tests/test_session_handoff.py`](../../tests/test_session_handoff.py)
- `test_registry_integration` — o Registry descobre a skill (válida, habilitada,
  `production`) e `load_executor` devolve o executor.
- `test_save_and_resume` — com SQLite real + Event Bus real: `save` persiste o
  handoff e emite `skill.session_handoff.created`; `resume` recupera e emite
  `skill.session_handoff.resumed`.
- `test_any_agent_can_call` — a skill roda com `caller` = secretary / zavix /
  orchestrator.

Rodar: `python tests/test_session_handoff.py` (ou via `pytest`).
