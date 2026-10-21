# GenResearch-Servidor (AV2 — Sistemas Operacionais 2026/2)

Serviço simplificado de RAG (ingestão → índice vetorial → fila → recuperação → geração → cache → log)
usado para **observar como o Linux administra memória, armazenamento, cache de páginas, filas e sincronização**.
O foco não é a qualidade da resposta, e sim o custo de sistema.

Vídeo: ver em `VIDEO.md` ou  (URL: https://drive.google.com/drive/folders/1_0rMmo7WNAwuof_MtavP9KYk2sW2omYC?usp=drive_link) · Autor: José Wallas · Trabalho individual

## Ambiente de referência
Fedora 44 Workstation, x86_64, 8 CPUs, 15 GiB RAM, swap de 8 GiB em **zram** (RAM comprimida, não é disco), SSD de 1 TB.
Python 3 + numpy + matplotlib. Ollama (opcional) com `phi4-mini`. O registro oficial fica em `evidencias/ambiente.txt`.

## Instalação
```bash
sudo dnf install -y python3 python3-pip strace sysstat   # strace e iostat são opcionais
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Reprodução (passo a passo)
```bash
bash scripts/00_ambiente.sh                  # Parte A: ambiente -> evidencias/ambiente.txt
python3 src/experimentos.py preparar         # corpora sintéticos + índices (pequeno/médio/grande)
python3 src/experimentos.py c1c2             # leitura convencional x mmap (no app)
python3 src/experimentos.py c3               # concorrência e fila: 1, 2, 4 workers
python3 src/experimentos.py c4               # cache compartilhado
python3 src/experimentos.py c5               # pressão de memória (corpus/contexto crescentes)
python3 src/experimentos.py c6               # falhas controladas
python3 src/mmap_vs_read.py                  # Parte E: read x mmap (cache frio/quente)
python3 src/sincronizacao.py                 # Parte D: corridas, deadlock, correções
python3 src/graficos.py                      # PNGs em resultados/graficos/
bash scripts/evidencias_execucao.sh          # threads, vmstat, iostat, strace
```
Atalho: `bash scripts/rodar_tudo.sh` (use `RAPIDO=1` para uma versão curta, sem corpus grande).
Cada configuração é repetida **3 vezes** (`--reps`). Cada execução roda em processo novo.

## Mapa: requisito → arquivo
| Parte | Onde |
|---|---|
| A — ambiente | `scripts/00_ambiente.sh`, `evidencias/ambiente.txt` |
| B — ingestão, armazenamento, fila, recuperação, resposta, cache, log | `src/genresearch.py` |
| C1/C2 — convencional x mmap | `experimentos.py c1c2` e `mmap_vs_read.py` |
| C3 — produtores/consumidores | `experimentos.py c3` (2 produtores; 1, 2, 4 workers) |
| C4 — cache | `experimentos.py c4` (repetidas x distintas; LRU x FIFO; capacidade) |
| C5 — pressão de memória | `experimentos.py c5` (corpus x contexto x mmap) |
| C6 — falhas | `experimentos.py c6` (arquivo ausente, fila saturada, serviço externo) |
| D — sincronização | `src/sincronizacao.py` (cache, log, buffer empty/full/mutex, deadlock) |
| E — memória virtual | `src/mmap_vs_read.py` |

## Decisões de projeto
- **Workers = threads.** A carga é mista: numpy e a espera da geração liberam a GIL. O modo `--gerador cpu` ocupa a CPU e mostra o limite das threads (C3). Processos seriam a alternativa para CPU pura.
- **BLAS com 1 thread** (`OPENBLAS_NUM_THREADS=1`) para evitar paralelismo aninhado.
- **Embeddings simulados** (hashing trick, determinísticos). Geração **simulada** (sleep/CPU) nos experimentos; **Ollama real** só em demonstração (`experimentos.py ollama --modelo phi4-mini`, nome conforme `ollama list`). O modelo roda no processo do Ollama, não no nosso (compare RSS com `ps`).
- **Cache frio sem root:** `posix_fadvise(DONTNEED)`. Para rigor extra: `mmap_vs_read.py --drop-caches` (usa sudo).
- **Dados 100% sintéticos** (`src/corpus_sintetico.py`, semente fixa). Nada de chaves, `.env` ou pesos de modelo no repositório.

## Observações e limitações
- C5 em 15 GiB não leva a swap real com segurança; o swap deste sistema é zram. Alternativa documentada: escalar corpus/contexto e observar RSS, faltas de página e MemAvailable. Justifique no relatório.
- `experimentos.py c6 --limite-memoria` (RLIMIT_AS) é **experimental** e pode falhar em bibliotecas nativas; não faz parte do padrão.
- Resultados valem para este hardware e carga sintética; não generalizam para modelos grandes, multi-GPU ou ambientes distribuídos.
