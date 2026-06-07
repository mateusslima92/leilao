#!/bin/bash
# DUPLO-CLIQUE para rodar o ciclo completo agora (baixar -> analisar -> enviar WhatsApp).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$DIR/rodar_diario.sh"
echo
echo "Concluído. Detalhes em rodar_diario.log. Pode fechar esta janela."
