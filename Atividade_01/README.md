# SO_UFS_2026_2_Silva_Wallas

Atividade 1 (AV1) — Sistemas Operacionais (UFS 2026.2)
Trilha A — Chat local: Ollama + Open WebUI
Modelo: Phi-4-mini-instruct (Microsoft, 3.8B, GGUF Q4_K_M)

Discente: José Wallas Cruz da Silva

## Vídeo da atividade

https://drive.google.com/drive/folders/1Ec1j0zYD94IpbTh_WV0odD96T1w74B9Q?usp=drive_link

## Estrutura do repositório

```
.
├── README.md
├── relatorio_final.pdf        
├── VIDEO.md
├── declaracao_uso_ia.md
├── ficha_aplicacao.md
├── scripts/
│   └── run_experimentos.sh
├── evidencias/
│   ├── ambiente.txt
│   ├── docker_logs_openwebui.txt
│   ├── ps_geral.txt
│   ├── ps_threads.txt
│   ├── pstree.txt
│   ├── strace-resumo.txt
│   ├── htop.png
│   └── top_H.png
├── dados/
│   ├── resultados.csv
│   └── logs/
└── .gitignore
```

## Ambiente utilizado

- Fedora Linux 44 (Workstation Edition), kernel 7.1.8-200.fc44
- CPU: Intel Core i5-1035G1 (4 núcleos físicos / 8 threads), sem GPU dedicada
- RAM: 15GiB, swap 8GiB via zram
- Docker 29.8.0, Ollama 0.34.1

Detalhes completos em `evidencias/ambiente.txt` e na Seção 5 do relatório.

## Como instalar e executar

### 1. Instalar o Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Se o Ollama precisar aceitar conexões vindas de um container Docker (erro
`Cannot connect to host.docker.internal:11434`), configure:

```bash
sudo systemctl edit ollama.service
```

E adicione:
```
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### 2. Baixar o modelo

```bash
ollama pull phi4-mini
```

### 3. Subir o Open WebUI

```bash
docker run -d -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

Acesse `http://localhost:3000`, crie a conta de administrador e selecione o
modelo `phi4-mini:latest`.

## Como reproduzir os experimentos (Parte C)

```bash
chmod +x scripts/run_experimentos.sh
./scripts/run_experimentos.sh
```

O script executa 12 rodadas automatizadas (3 configurações × 2 tamanhos ×
2 repetições) e salva:
- `dados/resultados.csv` — tabela consolidada com tempo total, uso de
  memória e threads por execução
- `dados/logs/` — saída completa de cada execução individual

Tempo estimado de execução: 15–25 minutos.

## Como reproduzir a Parte B (processos, threads, syscalls)

Ver instruções completas na Seção 8 do relatório. Resumo:

```bash
# Terminal 1 — inicia a captura de syscalls
sudo timeout 30 strace -f -c -p $(pgrep -x ollama) -o evidencias/strace-resumo.txt

# Terminal 2 — durante os 30s, enviar uma pergunta pela interface web
# e capturar processos/threads
ps -eo pid,ppid,stat,ni,pri,psr,pcpu,pmem,nlwp,comm --sort=-pcpu > evidencias/ps_geral.txt
ps -eLf > evidencias/ps_threads.txt
pstree -p > evidencias/pstree.txt
```

## Relatório completo

Ver `relatorio_final.pdf` para a documentação completa,
incluindo introdução, arquitetura, resultados dos 12 experimentos,
discussão e limitações.