#!/bin/bash
# Atalho de DUPLO-CLIQUE: baixa a lista PB da Caixa para "planilhas leilao".
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$DIR/baixar_csv.sh"
echo
echo "Pronto. Pode fechar esta janela."
