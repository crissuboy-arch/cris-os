# Regra permanente de Checkpoint Git

> Processo operacional para quem trabalha neste repositório (Cris ou Claude
> Code). Aplica-se a **todo o projeto CRIS OS** e a todas as fases futuras.

## Gatilho

Sempre que a Cris revisar uma etapa/projeto e disser explicitamente algo como:

- "Está OK"
- "Aprovado"
- "Pode finalizar"
- "Ficou certo"
- "Projeto aprovado"
- "Fase aprovada"

isso significa que chegamos a um **CHECKPOINT APROVADO**.

## O que fazer no checkpoint (nesta ordem)

1. **Parar** novas implementações.
2. Executar os **testes relevantes** da etapa.
3. Verificar `git status` e `git diff`.
4. Verificar se existem **alterações acidentais** (arquivos que não deveriam
   ter mudado, artefatos de debug, etc.).
5. Confirmar que `.env`, tokens, API keys, senhas e outros segredos **NÃO**
   serão commitados (checar `.gitignore`, `git ls-files`, e o diff staged).
6. Atualizar a **documentação correspondente** à etapa.
7. Criar um **commit claro** descrevendo o checkpoint aprovado.
8. Informar:
   - branch;
   - hash do commit;
   - arquivos alterados;
   - testes executados;
   - resultado;
   - pendências conhecidas.
9. Se o repositório remoto correto já estiver confirmado **e** a Cris tiver
   autorizado o fluxo de atualização do GitHub, fazer o `git push` normal do
   checkpoint.

## Regras rígidas (sem exceção)

- **NUNCA** usar force-push.
- **NUNCA** apagar histórico.
- **NUNCA** fazer reset destrutivo.
- **NUNCA** sobrescrever trabalho não relacionado.
- **NUNCA** incluir segredos no commit.
- Se houver conflito, erro, alteração inesperada ou dúvida sobre o
  repositório/branch: **PARAR** e informar a Cris antes de prosseguir.

## O que "OK/Aprovado" NÃO significa

"OK/Aprovado" significa: finalizar a etapa → testar → documentar →
checkpoint Git → atualizar o GitHub **somente quando autorizado**.

**Não significa** começar automaticamente a próxima fase. Depois do
checkpoint, aguardar o próximo comando da Cris.

## Precedente

Esta regra foi estabelecida em 17/09/2026, logo após o checkpoint do
[MARCO 1 — CRIS OS ↔ SCALAFLOW ↔ TELEGRAM](MARCO-01-TELEGRAM-SCALAFLOW.md)
(commit `61b0953`), que seguiu esse mesmo processo antes da regra existir
formalmente por escrito.
