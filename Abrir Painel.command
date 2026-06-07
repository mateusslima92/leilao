#!/bin/bash
# DUPLO-CLIQUE para abrir o painel com o botão "▶ Rodar agora" funcionando.
# Inicia o servidor local e abre o painel no navegador. Deixe esta janela aberta.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR" || exit 1
PY="$(command -v python3 || echo /usr/bin/python3)"

URL="http://127.0.0.1:8765/"
# Abre o navegador depois de 1s (dá tempo do servidor subir). Se já estiver no ar, só reabre.
( sleep 1; open "$URL" ) &

echo "Iniciando o painel… o navegador vai abrir em $URL"
echo "Mantenha esta janela ABERTA enquanto usa o painel. Feche-a para parar."
exec "$PY" server.py
