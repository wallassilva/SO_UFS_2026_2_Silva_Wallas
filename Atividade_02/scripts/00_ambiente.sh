#!/usr/bin/env bash
# Parte A: registra o ambiente em evidencias/ambiente.txt
cd "$(dirname "$0")/.." || exit 1
OUT=evidencias/ambiente.txt
{
  echo "### data: $(date -Is)"
  echo "### commit: $(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
  for c in "uname -a" "cat /etc/os-release" "lscpu" "free -h" "cat /proc/meminfo" "lsblk" "df -h" \
           "swapon --show" "zramctl" "findmnt -no FSTYPE,SOURCE /" "python3 --version" "pip list" \
           "ollama --version" "ollama list" "nvidia-smi" "vmstat 1 3" "iostat -xz 1 3"; do
    echo; echo "##### \$ $c"; bash -c "$c" 2>&1
  done
} > "$OUT"
echo "gravado em $OUT"
