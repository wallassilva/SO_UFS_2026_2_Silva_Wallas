# Atividade 3 - Virtualização, contêineres, namespaces e cgroups (SO 2026.2)
Aluno: José Wallas Cruz da Silva (trabalho individual) | Pasta: Atividade_03
Vídeo: https://drive.google.com/drive/u/1/folders/18qtkD42Jl1GFdvdB7v8gn-DEBJgQdAUN |Commit da entrega: HASH_DO_COMMIT
Imagem: python:3.12-slim fixada por digest:
  python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

## Preparação
Fedora 44 (Docker nativo 29.8.0, cgroup v2, driver systemd, SELinux Enforcing, sem GPU, sem VM).
sudo dnf install -y python3-matplotlib

## Reprodução (dentro de Atividade_03/)
1. source coleta_ambiente.sh          # ambiente + digest (IMAGEM_LAB)
2. bash evidencia_ns_mount.sh         # namespaces (Parte B) e read-only (Parte D)
3. bash confirmar_limites.sh          # limites efetivos do cgroup
4. export ITERACOES=60000000          # N congelado no piloto (resultados/N_congelado.txt)
5. bash run_experimentos.sh && python3 resumo.py   # 6 execuções C1/C2 + CSV + gráfico

## Coleta
resultados/namespaces, resultados/limites, resultados/piloto, resultados/bruto (JSON, CSV, gráfico)

## Observações
Sem LLM e sem GPU. Nenhuma execução foi descartada (seis válidas de seis).
