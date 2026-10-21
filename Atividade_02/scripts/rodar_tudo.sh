#!/usr/bin/env bash
# Reprodução completa. Use RAPIDO=1 para uma versão curta (sem corpus grande).
set -e
cd "$(dirname "$0")/.."
R=""; [ "${RAPIDO:-0}" = "1" ] && R="--rapido"
bash scripts/00_ambiente.sh
python3 src/experimentos.py tudo $R 2>&1 | tee resultados/logs/experimentos_stdout.txt
python3 src/mmap_vs_read.py 2>&1 | tee resultados/logs/mmap_vs_read_stdout.txt
python3 src/sincronizacao.py 2>&1 | tee resultados/logs/sincronizacao_stdout.txt
python3 src/graficos.py
echo "Pronto. Rode também: bash scripts/evidencias_execucao.sh"
