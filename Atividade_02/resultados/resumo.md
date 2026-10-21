
### Ingestão  (ingestao.csv, 2 linhas)

| configuração | n | n_docs | n_chunks | bytes_corpus | bytes_indice | t_embeddings_s | t_total_s |
|---|---|---|---|---|---|---|---|
| medio | 1 | 2000.00±0.00 | 50000.00±0.00 | 43987028.00±0.00 | 95939354.00±0.00 | 1.44±0.00 | 2.05±0.00 |
| pequeno | 1 | 500.00±0.00 | 5000.00±0.00 | 4399504.00±0.00 | 9595328.00±0.00 | 0.15±0.00 | 0.23±0.00 |

### mmap vs read  (mmap_vs_read.csv, 72 linhas)

| configuração | n | t_leitura_ms | rss_delta_mb | faltas_menores | faltas_maiores | io_disco_mb |
|---|---|---|---|---|---|---|
| 1024MB aleatorio frio mmap | 3 | 717.50±6.11 | 744.22±0.02 | 11573.00±2.94 | 382.00±0.00 | 1073.62±0.00 |
| 1024MB aleatorio frio read | 3 | 1288.91±3.28 | 0.06±0.00 | 1.00±0.00 | 0.00±0.00 | 162.57±0.00 |
| 1024MB aleatorio quente mmap | 3 | 41.88±0.37 | 745.06±0.00 | 11921.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| 1024MB aleatorio quente read | 3 | 29.05±0.31 | 0.06±0.00 | 1.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| 1024MB sequencial frio mmap | 3 | 648.98±29.58 | 1025.00±0.00 | 4755.00±0.00 | 1.00±0.00 | 1073.74±0.00 |
| 1024MB sequencial frio read | 3 | 644.62±4.06 | 0.18±0.00 | 1025.00±0.00 | 0.00±0.00 | 1073.74±0.00 |
| 1024MB sequencial quente mmap | 3 | 521.45±3.37 | 1024.29±0.00 | 4317.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| 1024MB sequencial quente read | 3 | 566.28±20.09 | -0.71±0.00 | 298.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| 16MB aleatorio frio mmap | 3 | 21.60±0.26 | 16.00±0.00 | 256.67±0.47 | 6.00±0.00 | 16.78±0.00 |
| 16MB aleatorio frio read | 3 | 98.26±0.62 | 0.06±0.00 | 1.00±0.00 | 0.00±0.00 | 16.78±0.00 |
| 16MB aleatorio quente mmap | 3 | 11.56±0.59 | 16.00±0.00 | 256.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| 16MB aleatorio quente read | 3 | 29.61±0.76 | 0.06±0.00 | 1.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| 16MB sequencial frio mmap | 3 | 13.62±0.44 | 17.00±0.00 | 723.33±0.47 | 1.00±0.00 | 16.78±0.00 |
| 16MB sequencial frio read | 3 | 13.73±0.11 | 0.18±0.00 | 1025.00±0.00 | 0.00±0.00 | 16.78±0.00 |
| 16MB sequencial quente mmap | 3 | 8.54±0.13 | 16.29±0.00 | 285.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| 16MB sequencial quente read | 3 | 9.12±0.05 | -0.71±0.00 | 298.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| 256MB aleatorio frio mmap | 3 | 183.91±12.91 | 254.35±0.02 | 4007.67±1.70 | 96.00±0.00 | 268.44±0.00 |
| 256MB aleatorio frio read | 3 | 986.95±2.16 | 0.06±0.00 | 1.00±0.00 | 0.00±0.00 | 214.83±0.00 |
| 256MB aleatorio quente mmap | 3 | 26.89±0.71 | 254.50±0.00 | 4072.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| 256MB aleatorio quente read | 3 | 33.63±0.85 | 0.06±0.00 | 1.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| 256MB sequencial frio mmap | 3 | 155.71±5.02 | 257.00±0.00 | 1683.33±0.47 | 1.00±0.00 | 268.44±0.00 |
| 256MB sequencial frio read | 3 | 159.26±1.45 | 0.18±0.00 | 1025.00±0.00 | 0.00±0.00 | 268.44±0.00 |
| 256MB sequencial quente mmap | 3 | 138.87±10.71 | 256.29±0.00 | 1245.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| 256MB sequencial quente read | 3 | 137.76±1.94 | -0.71±0.00 | 298.00±0.00 | 0.00±0.00 | 0.00±0.00 |

### C1/C2 (no app)  (c1c2.csv, 12 linhas)

| configuração | n | t_carga_indice_s | vazao_req_s | lat_p95_ms | rss_pico_mb | faltas_maiores_exec | io_read_mb |
|---|---|---|---|---|---|---|---|
| C1_read_medio_frio | 3 | 0.05±0.03 | 39.00±0.26 | 522.92±4.95 | 97.66±0.08 | 0.00±0.00 | 66.04±0.04 |
| C1_read_medio_quente | 3 | 0.01±0.00 | 40.98±0.24 | 499.70±11.94 | 97.40±0.30 | 0.00±0.00 | 0.00±0.00 |
| C2_mmap_medio_frio | 3 | 0.01±0.00 | 40.69±0.08 | 496.01±8.42 | 117.81±0.21 | 17.00±0.00 | 65.67±0.00 |
| C2_mmap_medio_quente | 3 | 0.00±0.00 | 41.20±0.30 | 497.71±9.53 | 117.91±0.10 | 0.00±0.00 | 0.00±0.00 |

### C3 concorrência  (c3.csv, 24 linhas)

| configuração | n | vazao_req_s | lat_mediana_ms | lat_p95_ms | espera_fila_media_ms | fila_media | fila_max | utilizacao_workers |
|---|---|---|---|---|---|---|---|---|
| cpu_w1_fila16 | 3 | 12.31±0.01 | 1539.68±1.50 | 1551.98±1.75 | 1273.56±0.55 | 14.50±0.00 | 16.00±0.00 | 1.00±0.00 |
| cpu_w2_fila16 | 3 | 17.23±0.07 | 1153.99±11.48 | 1199.06±16.73 | 901.45±3.14 | 14.49±0.01 | 16.00±0.00 | 0.99±0.00 |
| cpu_w4_fila16 | 3 | 27.47±1.04 | 752.00±34.09 | 880.42±31.06 | 546.33±21.84 | 14.32±0.04 | 16.00±0.00 | 0.98±0.00 |
| simulado_w1_fila16 | 3 | 11.63±0.00 | 1630.02±0.14 | 1650.55±1.52 | 1349.83±1.79 | 14.50±0.00 | 16.00±0.00 | 1.00±0.00 |
| simulado_w2_fila16 | 3 | 23.08±0.19 | 861.09±4.55 | 876.97±6.31 | 673.21±5.44 | 14.46±0.00 | 16.00±0.00 | 1.00±0.00 |
| simulado_w4_fila16 | 3 | 45.13±0.27 | 453.83±6.22 | 532.88±5.20 | 337.24±2.16 | 14.40±0.04 | 16.00±0.00 | 0.99±0.00 |
| simulado_w4_fila2 | 3 | 45.21±0.03 | 173.56±1.08 | 192.53±8.26 | 80.91±1.89 | 1.90±0.01 | 2.00±0.00 | 0.99±0.00 |
| simulado_w4_fila64 | 3 | 44.88±0.36 | 934.43±4.01 | 1522.06±14.13 | 818.58±2.26 | 38.65±0.12 | 64.00±0.00 | 0.99±0.01 |

### C4 cache  (c4.csv, 15 linhas)

| configuração | n | cache_taxa_acerto | cache_evicoes | cache_tempo_economizado_s | vazao_req_s | lat_p95_ms |
|---|---|---|---|---|---|---|
| cache200_lru_distintas | 3 | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 51.07±0.31 | 465.01±4.36 |
| cache200_lru_repetidas | 3 | 0.60±0.01 | 0.00±0.00 | 6.06±0.09 | 121.26±1.24 | 312.29±3.79 |
| cache20_fifo_repetidas | 3 | 0.40±0.01 | 53.33±1.25 | 3.98±0.07 | 84.80±0.88 | 316.04±1.94 |
| cache20_lru_repetidas | 3 | 0.45±0.01 | 47.67±1.25 | 4.42±0.09 | 91.49±1.75 | 314.89±3.76 |
| sem_cache_repetidas | 3 | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 52.54±0.06 | 446.54±1.65 |

### C5 pressão de memória  (c5.csv, 24 linhas)

| configuração | n | rss_pico_mb | vsz_pico_mb | memavail_min_mb | swap_usado_max_mb | faltas_maiores_exec | lat_p95_ms |
|---|---|---|---|---|---|---|---|
| medio_mmap_ctxleve | 3 | 110.07±0.04 | 1203.86±0.00 | 10445.70±7.05 | 0.00±0.00 | 16.33±1.89 | 237.43±3.99 |
| medio_mmap_ctxpesado | 3 | 137.66±0.19 | 1203.86±0.00 | 10411.37±8.92 | 0.00±0.00 | 18.00±1.41 | 873.17±5.51 |
| medio_read_ctxleve | 3 | 97.73±0.06 | 1161.45±0.36 | 10371.85±6.85 | 0.00±0.00 | 0.00±0.00 | 254.14±8.91 |
| medio_read_ctxpesado | 3 | 97.49±0.26 | 1161.70±0.36 | 10379.13±8.81 | 0.00±0.00 | 0.00±0.00 | 952.01±4.65 |
| pequeno_mmap_ctxleve | 3 | 56.05±0.02 | 1119.85±0.00 | 10115.69±5.24 | 0.00±0.00 | 2.00±0.00 | 187.21±2.47 |
| pequeno_mmap_ctxpesado | 3 | 55.98±0.08 | 1119.85±0.00 | 10175.57±63.55 | 0.00±0.00 | 2.00±0.00 | 816.97±0.74 |
| pequeno_read_ctxleve | 3 | 52.36±0.07 | 944.99±60.34 | 10127.63±5.90 | 0.00±0.00 | 0.00±0.00 | 193.08±0.60 |
| pequeno_read_ctxpesado | 3 | 52.38±0.03 | 1030.32±120.68 | 10098.08±16.20 | 0.00±0.00 | 0.00±0.00 | 829.78±3.22 |

### C6 falhas  (c6.csv, 18 linhas)

| configuração | n | status | n_enviadas | n_processadas | n_rejeitadas | n_retentativas_fila | n_falhas | perdidos |
|---|---|---|---|---|---|---|---|---|
| arquivo_ausente_com_fallback | 3 | recuperado_com_fallback | 40.00±0.00 | 40.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| arquivo_ausente_sem_fallback | 3 | falha_controlada | - | - | - | - | - | - |
| fila_saturada | 3 | ok | 13.00±0.00 | 13.00±0.00 | 27.00±0.00 | 71.00±0.00 | 0.00±0.00 | 0.00±0.00 |
| ollama_indisponivel | 3 | ok | 20.00±0.00 | 20.00±0.00 | 0.00±0.00 | 0.00±0.00 | 20.00±0.00 | 0.00±0.00 |
| servico_falha_com_retentativa | 3 | ok | 40.00±0.00 | 40.00±0.00 | 0.00±0.00 | 0.00±0.00 | 1.67±0.47 | 0.00±0.00 |
| servico_falha_sem_retentativa | 3 | ok | 40.00±0.00 | 40.00±0.00 | 0.00±0.00 | 0.00±0.00 | 22.00±0.00 | 0.00±0.00 |

### Sincronização: cache  (sincronizacao.csv, 30 linhas)

| configuração | n | tempo_s | atualizacoes_perdidas | computacoes_redundantes |
|---|---|---|---|---|
| lock_curto | 3 | 0.04±0.00 | 0.00±0.00 | 21.00±0.00 |
| lock_global | 3 | 0.12±0.00 | 0.00±0.00 | 0.00±0.00 |
| sem_lock | 3 | 0.04±0.00 | 1883.33±49.07 | 20.67±0.47 |
| ~ | 21 | 0.63±1.10 | - | - |

### Sincronização: log e buffer  (sincronizacao.csv, 30 linhas)

| configuração | n | linhas_corrompidas | itens_perdidos | itens_duplicados |
|---|---|---|---|---|
| buffer_limitado/com_mutex | 3 | - | 0.00±0.00 | 0.00±0.00 |
| buffer_limitado/consumidor_bloqueado | 3 | - | - | - |
| buffer_limitado/sem_mutex | 3 | - | 271.00±5.89 | 0.00±0.00 |
| log_concorrente/com_mutex | 3 | 0.00±0.00 | - | - |
| log_concorrente/sem_mutex | 3 | 6.00±0.82 | - | - |
| ~ | 15 | - | - | - |

### Sincronização: deadlock  (sincronizacao.csv, 30 linhas)

| configuração | n | deadlock_confirmado | tempo_s | deadlocks_detectados |
|---|---|---|---|---|
| deadlock/real_sem_timeout | 3 | True | 3.01±0.01 | - |
| deadlock/recuperavel_com_timeout | 3 |  | 0.74±0.01 | 1.00±0.00 |
| ~ | 24 |  | 0.04±0.04 | - |