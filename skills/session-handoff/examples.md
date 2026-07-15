# Exemplos — Session Handoff

> Exemplos concretos (entrada → saída). Base dos testes em [tests.md](tests.md).

## Exemplo 1 — Salvar (handoff)
- **Pedido:** "salva onde paramos: estava montando o post do VitrinePro, falta a legenda."
- **Entrada:**
  ```json
  {"action": "save", "notes": "post do VitrinePro quase pronto", "next_steps": ["escrever a legenda", "escolher a thumbnail"]}
  ```
- **Saída esperada:**
  ```json
  {"ok": true, "action": "save", "handoff_id": "<id>",
   "summary": "Sessão empacotada ✅ Próximos passos: escrever a legenda; escolher a thumbnail | Notas: post do VitrinePro quase pronto | N msgs, M itens do dia."}
  ```

## Exemplo 2 — Retomar (resume)
- **Pedido:** "retoma de onde eu parei."
- **Entrada:** `{"action": "resume"}`
- **Saída esperada:**
  ```json
  {"ok": true, "action": "resume", "found": true, "handoff_id": "<id>",
   "summary": "Retomando de <data> (por secretary). Próximos passos: escrever a legenda; escolher a thumbnail | Notas: post do VitrinePro quase pronto."}
  ```

## Exemplo 3 — Retomar sem histórico
- **Entrada:** `{"action": "resume"}` (sessão sem handoff salvo)
- **Saída esperada:** `{"ok": true, "action": "resume", "found": false, "summary": "Nenhum handoff salvo para esta sessão ainda."}`
