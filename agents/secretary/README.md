# 💛 Agente: Secretária IA da Cris

**Status:** ✅ Funcional (primeiro agente do CRIS OS)
**Canal:** Telegram
**Modelo:** Ollama (local)

## O que ela faz
- Conversa com a Cris pelo Telegram, com tom humano e organizado.
- Transforma mensagens soltas em **plano de ação**.
- Define **prioridades** e separa tarefas **pessoais x negócio**.
- Agrupa tarefas por **projeto** (Zavix, VitrinePro, ScalaFlow, etc.).
- Lembra de **caminhada, água, descanso e compromissos**.
- Ajuda com **posts, vendas e produção**.

## Arquivos
- `SYSTEM.md` — o prompt de comportamento (a "alma" da secretária).
- `README.md` — este arquivo.

## Como o comportamento é definido
O `loader` monta a Secretária como um `BaseAgent` usando este `SYSTEM.md`. Quando
o gerente (Orquestrador) delega uma tarefa a ela, o `SYSTEM.md` vira a instrução
de sistema, somado à **memória permanente** relevante e ao histórico recente da
conversa. A `description` do `manifest.json` é o que o gerente usa para decidir
quando acionar a Secretária.

## Como ajustar a personalidade
Edite o `SYSTEM.md`. Não precisa mexer no código Python. Ao salvar e reiniciar
o `main.py`, as mudanças já valem.

## Próximos passos (TODO)
- [ ] Lembretes com horário.
- [ ] Encaminhar tarefas para os agentes de cada projeto.
- [ ] Memória de longo prazo (rotina, preferências, metas).
