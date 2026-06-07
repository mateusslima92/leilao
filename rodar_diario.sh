#!/bin/bash
# Ciclo diário COMPLETO do Leilão PB — 100% no seu Mac, sem Cowork e sem Chrome:
#   1) baixa o CSV (link direto da Caixa)  2) analisa + aplica alarmes + monta a fila
#   3) envia o WhatsApp (idempotente)      4) fixa o baseline (novos de hoje != novos amanhã)
# Tudo é registrado em rodar_diario.log.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR" || exit 1
LOG="$DIR/rodar_diario.log"
PY="$(command -v python3 || echo /usr/bin/python3)"
ts(){ date '+%d/%m/%Y %H:%M:%S'; }

echo "================ $(ts) — INÍCIO ================" >> "$LOG"

# 1) Download (best-effort: se falhar, segue com o CSV mais recente já em 'planilhas leilao')
if bash "$DIR/baixar_csv.sh" >> "$LOG" 2>&1; then
  echo "[$(ts)] 1/4 download OK" >> "$LOG"
else
  echo "[$(ts)] 1/4 download falhou — usando o CSV mais recente disponível" >> "$LOG"
fi

# 2) Análise + fila de WhatsApp (gera whatsapp_outbox.json e atualiza o painel)
if ! "$PY" leilao_routine.py prepare >> "$LOG" 2>&1; then
  echo "[$(ts)] 2/4 prepare FALHOU (provavelmente nenhum CSV). Abortando antes de enviar." >> "$LOG"
  echo "================ $(ts) — FIM (erro) ================" >> "$LOG"
  exit 2
fi
echo "[$(ts)] 2/4 prepare OK" >> "$LOG"

# 3) Envio do WhatsApp (só manda o que estiver na fila; idempotente via whatsapp_sent.json)
"$PY" whatsapp_sender.py >> "$LOG" 2>&1
echo "[$(ts)] 3/4 envio concluído (rc=$?)" >> "$LOG"

# 4) Fixa o baseline (depois de enviar, para não reavisar amanhã as mesmas)
"$PY" leilao_routine.py commit >> "$LOG" 2>&1
echo "[$(ts)] 4/4 baseline fixado" >> "$LOG"

echo "================ $(ts) — FIM ================" >> "$LOG"
