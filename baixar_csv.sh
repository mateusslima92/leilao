#!/bin/bash
# Baixa a lista de imóveis PB da Caixa pelo LINK DIRETO e salva em "planilhas leilao"
# com carimbo de data. Roda no SEU Mac (que tem internet aberta).
#
# A Caixa usa um anti-robô (Radware Bot Manager) que, de vez em quando, devolve uma
# PÁGINA DE CAPTCHA (HTML ~18 KB) no lugar do CSV. Para lidar com isso, este script:
#   1) "aquece" uma sessão de navegador (pega cookies na página de download);
#   2) baixa o CSV mandando headers de navegador (User-Agent, Referer, etc.);
#   3) tenta de novo (até 4x) se vier CAPTCHA/HTML;
#   4) VALIDA de verdade: rejeita CAPTCHA/HTML e exige tamanho + conteúdo de CSV real.
# Se nada válido vier, sai com erro e NÃO salva lixo (o ciclo usa o último CSV bom).
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$DIR/planilhas leilao"
URL="https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_PB.csv"
PAGE="https://venda-imoveis.caixa.gov.br/sistema/download-lista.asp"
ORIGIN="https://venda-imoveis.caixa.gov.br/"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

mkdir -p "$DEST"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$DEST/Lista_imoveis_PB_${TS}.csv"
JAR="$(mktemp -t leilao_cookies.XXXXXX)"
trap 'rm -f "$JAR"' EXIT

ts(){ date '+%d/%m/%Y %H:%M:%S'; }

# Considera o download válido? (0 = sim). Rejeita CAPTCHA/HTML; exige CSV plausível.
is_valid_csv() {
  local f="$1"
  [ -s "$f" ] || return 1
  local sz; sz=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
  # página anti-robô / HTML?
  if head -c 3000 "$f" | grep -qiE "radware|captcha|bot manager|<html|<head|<!doctype|window\.SSJSInternal"; then
    echo "  → veio página anti-robô (CAPTCHA), não o CSV."
    return 1
  fi
  # CSV real tem ~300 KB; abaixo de 100 KB é suspeito
  if [ "${sz:-0}" -lt 100000 ]; then
    echo "  → arquivo pequeno demais (${sz} bytes) para ser a lista completa."
    return 1
  fi
  # tem cara de CSV da Caixa? (cabeçalhos típicos)
  if ! head -c 6000 "$f" | iconv -f latin1 -t utf-8 2>/dev/null | grep -qiE "endere|bairro|munic|valor|im[oó]vel"; then
    echo "  → conteúdo não parece a lista de imóveis da Caixa."
    return 1
  fi
  return 0
}

echo "[$(ts)] Baixando $URL"

# Conjunto de headers de navegador real (Chrome no macOS) — ajuda a passar pelo Radware.
CH_HEADERS=(
  -H 'sec-ch-ua: "Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"'
  -H 'sec-ch-ua-mobile: ?0'
  -H 'sec-ch-ua-platform: "macOS"'
  -H 'Upgrade-Insecure-Requests: 1'
  -H 'Accept-Language: pt-BR,pt;q=0.9,en;q=0.8'
)

ATTEMPTS=4
for n in $(seq 1 $ATTEMPTS); do
  # 1) aquece a sessão como um navegador: home -> página de download (acumula cookies)
  curl -fsSL -A "$UA" -c "$JAR" -b "$JAR" "${CH_HEADERS[@]}" \
       -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' \
       -H 'Sec-Fetch-Dest: document' -H 'Sec-Fetch-Mode: navigate' \
       -H 'Sec-Fetch-Site: none' -H 'Sec-Fetch-User: ?1' \
       --connect-timeout 20 --max-time 60 "$ORIGIN" -o /dev/null 2>/dev/null || true
  sleep 1
  curl -fsSL -A "$UA" -c "$JAR" -b "$JAR" "${CH_HEADERS[@]}" \
       -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' \
       -e "$ORIGIN" -H "Referer: $ORIGIN" \
       -H 'Sec-Fetch-Dest: document' -H 'Sec-Fetch-Mode: navigate' \
       -H 'Sec-Fetch-Site: same-origin' -H 'Sec-Fetch-User: ?1' \
       --connect-timeout 20 --max-time 60 "$PAGE" -o /dev/null 2>/dev/null || true
  sleep 1

  # 2) baixa o CSV com cara de navegador, usando os cookies da sessão
  curl -fSL --connect-timeout 20 --max-time 120 \
       -A "$UA" -e "$PAGE" -b "$JAR" -c "$JAR" "${CH_HEADERS[@]}" \
       -H "Accept: text/csv,application/octet-stream,application/vnd.ms-excel,*/*" \
       -H "Referer: $PAGE" \
       -H 'Sec-Fetch-Dest: empty' -H 'Sec-Fetch-Mode: cors' -H 'Sec-Fetch-Site: same-origin' \
       -o "$OUT" "$URL" 2>/dev/null || true

  if is_valid_csv "$OUT"; then
    SZ=$(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT" 2>/dev/null || echo 0)
    echo "[$(ts)] OK: $OUT (${SZ} bytes) — tentativa $n/$ATTEMPTS"
    exit 0
  fi

  echo "[$(ts)] tentativa $n/$ATTEMPTS não trouxe um CSV válido."
  rm -f "$OUT"
  # backoff mais longo: bloqueio anti-robô costuma ser temporário (15s, 30s, 45s)
  [ "$n" -lt "$ATTEMPTS" ] && sleep $((n*15))
done

echo "[$(ts)] ERRO: a Caixa não devolveu um CSV válido em $ATTEMPTS tentativas (provável bloqueio anti-robô temporário). Nada foi salvo — o ciclo seguirá com o último CSV bom."
exit 1
