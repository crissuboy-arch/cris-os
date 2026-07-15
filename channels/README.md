# 📡 channels/ — Canais de comunicação

Adaptadores de **entrada/saída** com a Cris. Cada canal implementa a porta
[core/contracts/channel.py](../core/contracts/channel.py) e só faz uma coisa:
traduzir a plataforma ↔ `IncomingMessage` e chamar o `Gateway`.

| Canal | Status | Pasta |
|---|---|---|
| Telegram | ✅ Funcional | `channels/telegram/` |
| WhatsApp | 🔴 Planejado | `channels/whatsapp/` |
| Discord | 🔴 Planejado | `channels/discord/` |
| Email | 🔴 Planejado | `channels/email/` |
| Instagram (DM) | 🔴 Planejado | `channels/instagram/` |

## Como adicionar um canal novo (próximas fases)
1. Criar `channels/<nome>/bot.py` com uma classe que cumpra a porta `Channel`
   (atributo `name` + método `run()`).
2. Receber o `handler` (Gateway.handle) por injeção e chamá-lo com uma
   `IncomingMessage` normalizada.
3. Registrar o canal em [core/runtime.py](../core/runtime.py).

> O núcleo não muda ao adicionar canais — esse é o objetivo da arquitetura.
> TODO: suporte a mensagens proativas (lembretes que o sistema envia sem você
> pedir) via um método `send(OutgoingMessage)` na porta.
