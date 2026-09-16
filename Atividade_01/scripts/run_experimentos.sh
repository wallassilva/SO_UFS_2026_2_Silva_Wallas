# =====================================================================
# Script de automação - Parte C (12 experimentos)
# Atividade 1 (AV1) - Sistemas Operacionais - UFS 2026.2
# Discente: José Wallas Cruz da Silva
#
# O QUE ESTE SCRIPT FAZ:
#   Roda o modelo phi4-mini via `ollama run` em 3 configurações,
#   com 2 tamanhos de entrada e 2 repetições cada = 12 execuções.
#   Para cada execução, mede:
#     - tempo total (real)
#     - snapshot de CPU/RAM/threads do processo ollama ANTES/DEPOIS
#   e salva tudo em dados/resultados.csv + logs individuais.
#
# COMO USAR:
#   1) chmod +x run_experimentos.sh
#   2) ./run_experimentos.sh
# =====================================================================

set -uo pipefail

BASE_DIR="$(pwd)"
DADOS_DIR="${BASE_DIR}/dados"
LOGS_DIR="${DADOS_DIR}/logs"
CSV="${DADOS_DIR}/resultados.csv"
MODEL="phi4-mini"

mkdir -p "${LOGS_DIR}"

# Cabeçalho do CSV (uma linha por execução)
if [ ! -f "${CSV}" ]; then
  echo "config,tamanho_entrada,repeticao,timestamp_inicio,tempo_total_s,pmem_ollama_antes,pmem_ollama_depois,nlwp_ollama_depois,log_file" > "${CSV}"
fi

# ---------------------------------------------------------------------
# Prompts de entrada: um curto e um longo
# ---------------------------------------------------------------------
PROMPT_CURTO="Explique em 2 frases o que é um processo em sistemas operacionais."
PROMPT_LONGO="Explique detalhadamente, em pelo menos 5 parágrafos, as diferenças entre processos e threads em sistemas operacionais, cobrindo criação, espaço de memória, comunicação, custo de troca de contexto e exemplos práticos de uso em aplicações modernas de IA generativa executadas localmente."

# ---------------------------------------------------------------------
# Função auxiliar: roda uma execução e mede tudo
# args: config_nome  tamanho_label  prompt_texto  repeticao  [flags_extra_ollama]
# ---------------------------------------------------------------------
run_experimento() {
  local config="$1"
  local tamanho="$2"
  local prompt="$3"
  local rep="$4"
  local extra_env="${5:-}"

  local ts
  ts=$(date +%Y%m%d_%H%M%S)
  local logfile="${LOGS_DIR}/${config}_${tamanho}_rep${rep}_${ts}.log"

  echo ""
  echo "=============================================================="
  echo ">> Config: ${config} | Tamanho: ${tamanho} | Repetição: ${rep}"
  echo "=============================================================="

  # snapshot ANTES (uso de memória do processo ollama, em %)
  local pmem_antes
  pmem_antes=$(ps -eo comm,pmem --no-headers | grep -i '^ollama' | head -1 | awk '{print $2}')
  [ -z "${pmem_antes}" ] && pmem_antes="NA"

  # mede o tempo total da execução (carregamento + geração da resposta)
  local inicio fim tempo_total
  inicio=$(date +%s.%N)

  if [ -n "${extra_env}" ]; then
    eval "${extra_env} ollama run ${MODEL} \"${prompt}\"" > "${logfile}" 2>&1
  else
    ollama run "${MODEL}" "${prompt}" > "${logfile}" 2>&1
  fi

  fim=$(date +%s.%N)
  tempo_total=$(echo "${fim} - ${inicio}" | bc)

  # snapshot DEPOIS
  local pmem_depois nlwp_depois
  pmem_depois=$(ps -eo comm,pmem --no-headers | grep -i '^ollama' | head -1 | awk '{print $2}')
  nlwp_depois=$(ps -eo comm,nlwp --no-headers | grep -i '^ollama' | head -1 | awk '{print $2}')
  [ -z "${pmem_depois}" ] && pmem_depois="NA"
  [ -z "${nlwp_depois}" ] && nlwp_depois="NA"

  echo "${config},${tamanho},${rep},${ts},${tempo_total},${pmem_antes},${pmem_depois},${nlwp_depois},${logfile}" >> "${CSV}"

  echo "Tempo total: ${tempo_total}s | pmem antes/depois: ${pmem_antes}/${pmem_depois} | threads depois: ${nlwp_depois}"

  # pausa entre execuções pra sistema "esfriar" e não poluir a próxima medição
  sleep 5
}

echo "Iniciando bateria de 12 experimentos. Resultados em: ${CSV}"
echo "Log individual de cada execução em: ${LOGS_DIR}"

# =====================================================================
# CONFIGURAÇÃO 1 - Padrão (baseline, sem alterações) -> 4 execuções
# =====================================================================
run_experimento "config1_padrao" "curto" "${PROMPT_CURTO}" "1"
run_experimento "config1_padrao" "curto" "${PROMPT_CURTO}" "2"
run_experimento "config1_padrao" "longo" "${PROMPT_LONGO}"  "1"
run_experimento "config1_padrao" "longo" "${PROMPT_LONGO}"  "2"

# =====================================================================
# CONFIGURAÇÃO 2 - Concorrência / carga controlada -> 4 execuções
# Aqui simulamos carga concorrente disparando 2 requisições em paralelo
# (ajuste conforme quiser: pode ser OLLAMA_NUM_PARALLEL também)
# =====================================================================
run_experimento_concorrente() {
  local tamanho="$1"
  local prompt="$2"
  local rep="$3"
  local ts
  ts=$(date +%Y%m%d_%H%M%S)
  local log1="${LOGS_DIR}/config2_concorrencia_${tamanho}_rep${rep}_A_${ts}.log"
  local log2="${LOGS_DIR}/config2_concorrencia_${tamanho}_rep${rep}_B_${ts}.log"

  echo ""
  echo "=============================================================="
  echo ">> Config: config2_concorrencia (2 requisições simultâneas) | Tamanho: ${tamanho} | Repetição: ${rep}"
  echo "=============================================================="

  local pmem_antes
  pmem_antes=$(ps -eo comm,pmem --no-headers | grep -i '^ollama' | head -1 | awk '{print $2}')
  [ -z "${pmem_antes}" ] && pmem_antes="NA"

  local inicio fim tempo_total
  inicio=$(date +%s.%N)

  ollama run "${MODEL}" "${prompt}" > "${log1}" 2>&1 &
  local pid1=$!
  ollama run "${MODEL}" "${prompt}" > "${log2}" 2>&1 &
  local pid2=$!
  wait "${pid1}" "${pid2}"

  fim=$(date +%s.%N)
  tempo_total=$(echo "${fim} - ${inicio}" | bc)

  local pmem_depois nlwp_depois
  pmem_depois=$(ps -eo comm,pmem --no-headers | grep -i '^ollama' | head -1 | awk '{print $2}')
  nlwp_depois=$(ps -eo comm,nlwp --no-headers | grep -i '^ollama' | head -1 | awk '{print $2}')
  [ -z "${pmem_depois}" ] && pmem_depois="NA"
  [ -z "${nlwp_depois}" ] && nlwp_depois="NA"

  echo "config2_concorrencia,${tamanho},${rep},${ts},${tempo_total},${pmem_antes},${pmem_depois},${nlwp_depois},${log1};${log2}" >> "${CSV}"
  echo "Tempo total (2 reqs em paralelo): ${tempo_total}s"

  sleep 5
}

run_experimento_concorrente "curto" "${PROMPT_CURTO}" "1"
run_experimento_concorrente "curto" "${PROMPT_CURTO}" "2"
run_experimento_concorrente "longo" "${PROMPT_LONGO}"  "1"
run_experimento_concorrente "longo" "${PROMPT_LONGO}"  "2"

# =====================================================================
# CONFIGURAÇÃO 3 - Ajuste de execução (contexto curto vs longo via
# num_ctx) -> 4 execuções. Aqui variamos o parâmetro de contexto do
# modelo usando a API /api/generate diretamente com "options".
# =====================================================================
run_experimento_contexto() {
  local tamanho="$1"
  local prompt="$2"
  local rep="$3"
  local num_ctx="$4"
  local ts
  ts=$(date +%Y%m%d_%H%M%S)
  local logfile="${LOGS_DIR}/config3_ctx${num_ctx}_${tamanho}_rep${rep}_${ts}.json"

  echo ""
  echo "=============================================================="
  echo ">> Config: config3_ajuste (num_ctx=${num_ctx}) | Tamanho: ${tamanho} | Repetição: ${rep}"
  echo "=============================================================="

  local pmem_antes
  pmem_antes=$(ps -eo comm,pmem --no-headers | grep -i '^ollama' | head -1 | awk '{print $2}')
  [ -z "${pmem_antes}" ] && pmem_antes="NA"

  local inicio fim tempo_total
  inicio=$(date +%s.%N)

  curl -s http://127.0.0.1:11434/api/generate -d "{
    \"model\": \"${MODEL}\",
    \"prompt\": \"${prompt}\",
    \"stream\": false,
    \"options\": { \"num_ctx\": ${num_ctx} }
  }" > "${logfile}"

  fim=$(date +%s.%N)
  tempo_total=$(echo "${fim} - ${inicio}" | bc)

  local pmem_depois nlwp_depois
  pmem_depois=$(ps -eo comm,pmem --no-headers | grep -i '^ollama' | head -1 | awk '{print $2}')
  nlwp_depois=$(ps -eo comm,nlwp --no-headers | grep -i '^ollama' | head -1 | awk '{print $2}')
  [ -z "${pmem_depois}" ] && pmem_depois="NA"
  [ -z "${nlwp_depois}" ] && nlwp_depois="NA"

  echo "config3_ctx${num_ctx},${tamanho},${rep},${ts},${tempo_total},${pmem_antes},${pmem_depois},${nlwp_depois},${logfile}" >> "${CSV}"
  echo "Tempo total (num_ctx=${num_ctx}): ${tempo_total}s"

  sleep 5
}

# contexto pequeno (2048) x contexto grande (8192), 2 repetições cada
run_experimento_contexto "curto" "${PROMPT_CURTO}" "1" 2048
run_experimento_contexto "curto" "${PROMPT_CURTO}" "2" 2048
run_experimento_contexto "longo" "${PROMPT_LONGO}"  "1" 8192
run_experimento_contexto "longo" "${PROMPT_LONGO}"  "2" 8192

echo ""
echo "=============================================================="
echo "TODOS OS 12 EXPERIMENTOS CONCLUÍDOS."
echo "Resultados consolidados em: ${CSV}"
echo "Logs individuais em: ${LOGS_DIR}"
echo "=============================================================="
