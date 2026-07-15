# 🧠 MODELOS.md — Modelos de IA do CRIS OS

Guia prático de qual modelo o CRIS OS usa, por que, e como evoluir. O Ollama roda
**fixado em CPU** nesta máquina (a GPU dá `CUDA out of memory`); ver
[BOOTSTRAP_FASE1.md](BOOTSTRAP_FASE1.md) e `scripts/start_ollama_cpu.cmd`.

---

## ✅ Modelo atual funcional: `qwen2.5-coder:1.5b`
- Tamanho: ~986 MB (≈1.2 GB carregado), roda **100% em CPU**.
- É o que **cabe na memória** desta máquina hoje e mantém a Fase 1 no ar.
- **Limitações:** é pequeno e voltado a *código*. **Não faz tool-calling**, então o
  Orquestrador **não delega de verdade** — cai no **fallback por palavra-chave**
  ([core/router.py](core/router.py)). A persona da Secretária fica fraca e às vezes
  responde em outro idioma. Serve bem para **validar o fluxo** da Fase 1.

No `.env`:
```
OLLAMA_MODEL=qwen2.5-coder:1.5b
OLLAMA_NUM_GPU=0
```

---

## 🎯 Modelo recomendado (futuro): `llama3.1` (8B)
- **Já foi baixado** (`ollama pull llama3.1`, 4.9 GB) — está no `ollama list`.
- **Por que vale:** faz **tool-calling de verdade** → o Orquestrador passa a
  **delegar** ao agente certo (ex.: "organize meu dia" vai para a Secretária, não
  para o Zavix por causa de uma palavra). Também tem PT-BR muito melhor.
- **Status:** **não carrega ainda** nesta máquina por limite de memória (abaixo).
- Para ativar quando a memória permitir: trocar no `.env` para `OLLAMA_MODEL=llama3.1`
  e reiniciar (`python main.py`).

---

## ⚠️ O problema: memória **comprometida (commit / page file)**, não GPU nem RAM física
Diagnóstico medido nesta máquina:
- RAM total: **31,9 GB** · RAM física **livre: ~13,7 GB** (sobra bastante).
- **Commit (em uso / limite): 34,4 / 35,8 GB** → só **~1,4 GB de folga** de *commit*.
- Ao carregar o llama3.1, o Ollama tentou alocar um buffer de **~3,36 GB**
  (`CPU_REPACK`) e **falhou**, porque não havia *commit* disponível.

**Tradução:** o Windows limita a memória que pode ser "prometida" aos programas
(*commit charge*) = RAM física **+ arquivo de paginação (page file)**. Aqui o page
file é pequeno, então o limite de commit (35,8 GB) está quase no teto. Mesmo com
13,7 GB de RAM física livre, o sistema **não promete** os ~8 GB que o modelo 8B
precisa. **Não é a GPU** (já está desligada) **nem falta de RAM física** — é o
**page file pequeno**.

---

## 🔧 Como aumentar o page file no Windows (correção robusta)
Isso eleva o limite de commit e permite carregar o llama3.1. Passo a passo:

1. Tecla **Windows** → digite **"Editar as configurações avançadas do sistema"** → abra.
2. Aba **Avançado** → seção **Desempenho** → botão **Configurações…**.
3. Aba **Avançado** → seção **Memória virtual** → botão **Alterar…**.
4. **Desmarque** "Gerenciar automaticamente o tamanho do arquivo de paginação".
5. Selecione o disco **C:** → marque **Tamanho personalizado**:
   - **Inicial (MB):** `8192`
   - **Máximo (MB):** `32768`  (pode usar até ~`49152`)
6. Clique **Definir** → **OK** em todas as janelas.
7. **Reinicie** o computador (obrigatório para valer).

Depois do reboot: `scripts\start_ollama_cpu.cmd`, troque o `.env` para
`OLLAMA_MODEL=llama3.1` e rode `python main.py`. (Dica: feche abas pesadas do
Chrome para sobrar memória; o 8B em CPU é mais lento — respostas em ~30–60 s.)

> Alternativa sem reboot: **liberar RAM** fechando apps pesados (Chrome costuma
> usar vários GB) pode abrir folga de commit suficiente — menos confiável que o page file.

---

## 🧪 Opções de modelos menores para testar (com tool-calling)
Se não quiser mexer no page file agora, dá para subir um modelo **menor que o 8B**
que ainda **faz tool-calling** (melhor que o coder atual). Baixe e troque no `.env`:

| Modelo | `ollama pull` | Tamanho | Tool-calling | Observação |
|---|---|---|---|---|
| `qwen2.5:1.5b` | `ollama pull qwen2.5:1.5b` | ~1 GB | sim (básico) | **geral** (não-coder); cabe igual ao atual, persona melhor |
| `llama3.2:1b` | `ollama pull llama3.2:1b` | ~1.3 GB | sim (limitado) | minúsculo, bom para testar delegação |
| `llama3.2:3b` | `ollama pull llama3.2:3b` | ~2 GB | sim | melhor qualidade; precisa de **um pouco mais de commit** |
| `qwen2.5:3b` | `ollama pull qwen2.5:3b` | ~2 GB | sim | alternativa ao llama3.2:3b |

**Como trocar de modelo:**
1. `ollama pull <modelo>`
2. No `.env`: `OLLAMA_MODEL=<modelo>`
3. Reinicie: pare o `main.py` e rode de novo `python main.py`.
4. Confira com `python scripts/preflight.py` e `ollama ps` (deve aparecer `100% CPU`).

> Recomendação prática: comece por `qwen2.5:1.5b` (cabe já e dá tool-calling básico)
> ou, após ajustar o page file, vá direto para `llama3.2:3b` / `llama3.1`.

---

## 📌 Resumo
| Item | Estado |
|---|---|
| Modelo em uso | `qwen2.5-coder:1.5b` (CPU, funciona, sem delegação real) |
| Modelo-alvo | `llama3.1` (baixado; aguarda ajuste de page file) |
| Bloqueio | limite de **commit/page file** do Windows (~1,4 GB de folga) |
| Correção | aumentar o page file (e/ou liberar RAM) → reboot |
| Atalho | testar `qwen2.5:1.5b` / `llama3.2:3b` como passo intermediário |
