#!/usr/bin/env bash
# Parte A: registra ambiente (sem hostname/machine-id) e fixa a imagem por digest.
# Uso: source coleta_ambiente.sh   (o "source" mantem IMAGEM_LAB exportada na sua shell)
mkdir -p ambiente
docker pull python:3.12-slim
export IMAGEM_LAB="$(docker image inspect --format '{{index .RepoDigests 0}}' python:3.12-slim)"
{
  echo "# coletado em $(date -Is)"
  uname -srvm
  grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release
  echo "virtualizacao=$(systemd-detect-virt)   # none = sem VM"
  echo "CPUs logicas=$(nproc)"; free -h | head -2
  echo "SELinux=$(getenforce 2>/dev/null)"
  echo "cgroup_fs=$(stat -fc %T /sys/fs/cgroup)   # cgroup2fs = v2"
  echo "controladores=$(cat /sys/fs/cgroup/cgroup.controllers)"
  docker version --format 'Docker cliente={{.Client.Version}} servidor={{.Server.Version}}'
  docker compose version 2>/dev/null
  docker info --format 'Cgroup={{.CgroupVersion}} Driver={{.CgroupDriver}} Runtime={{.DefaultRuntime}} Security={{.SecurityOptions}}'
  docker context show
  echo "IMAGEM_LAB=$IMAGEM_LAB"
  echo "commit=$(git rev-parse HEAD 2>/dev/null || echo ainda-sem-commit)"
} | tee ambiente/ambiente.txt
