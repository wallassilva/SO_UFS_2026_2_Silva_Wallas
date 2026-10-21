#!/usr/bin/env python3
"""GenResearch-Servidor: serviço simplificado de RAG para estudo de SO.

Subcomandos:
    ingerir   lê documentos, fragmenta, gera embeddings simulados e grava o índice
    executar  sobe produtores, fila limitada, consumidores (workers), cache
              compartilhado e log, processa uma carga de consultas e salva
              métricas em JSON.

Exemplos:
    python src/genresearch.py ingerir --corpus dados/corpus_pequeno --indice dados/indice_pequeno
    python src/genresearch.py executar --indice dados/indice_pequeno --workers 4 --usar-mmap

Decisões de projeto (justificadas no README):
  * BLAS com 1 thread (evita paralelismo aninhado e deixa o efeito dos workers visível).
  * Workers = threads: a carga é mista (numpy/E-S liberam a GIL; a geração simulada
    espera como uma E/S). O modo "cpu" mostra o limite das threads por causa da GIL.
  * Embeddings simulados por "hashing trick" (determinísticos, sem baixar modelo).
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import json
import mmap
import queue
import random
import re
import resource
import subprocess
import sys
import threading
import time
import urllib.request
import zlib
from collections import OrderedDict
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus_sintetico import montar_carga  # noqa: E402

DIM = 256
RAIZ = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------------------
# Leitura de métricas do sistema operacional (/proc)
# ----------------------------------------------------------------------------
def ler_meminfo():
    d = {}
    with open("/proc/meminfo") as f:
        for linha in f:
            k, v = linha.split(":")
            d[k] = int(v.split()[0])  # kB
    return d


def ler_vmstat():
    chaves = {"pgfault", "pgmajfault", "pswpin", "pswpout", "pgpgin", "pgpgout"}
    d = {}
    with open("/proc/vmstat") as f:
        for linha in f:
            k, v = linha.split()
            if k in chaves:
                d[k] = int(v)
    return d


def ler_status_proc():
    d = {}
    with open("/proc/self/status") as f:
        for linha in f:
            if linha.startswith(("VmRSS", "VmSize", "VmHWM", "VmPeak", "RssFile",
                                 "RssAnon", "VmData", "Threads")):
                k, v = linha.split(":")
                d[k] = int(v.split()[0])
    return d


def ler_io_proc():
    d = {}
    try:
        with open("/proc/self/io") as f:
            for linha in f:
                k, v = linha.split(":")
                d[k] = int(v)
    except OSError:
        pass
    return d


def foto():
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return {"t": time.perf_counter(), "status": ler_status_proc(), "io": ler_io_proc(),
            "minflt": ru.ru_minflt, "majflt": ru.ru_majflt,
            "meminfo": ler_meminfo(), "vmstat": ler_vmstat()}


def fadvise_dontneed(caminho):
    """Pede ao kernel para tirar do cache de páginas as páginas limpas do arquivo
    (não exige root). Usado para começar uma execução com cache 'frio'."""
    try:
        fd = os.open(str(caminho), os.O_RDONLY)
        try:
            os.fsync(fd)
        except OSError:
            pass
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        os.close(fd)
    except OSError:
        pass


def mb(kb):
    return round(kb / 1024.0, 2)


class Monitor(threading.Thread):
    """Amostra RSS, MemAvailable, swap e cache a cada `intervalo` segundos."""

    def __init__(self, intervalo=0.1):
        super().__init__(name="monitor", daemon=True)
        self.intervalo = intervalo
        self.parar = threading.Event()
        self.rss_max = 0
        self.memavail_min = None
        self.swap_max = 0
        self.cache_max = 0

    def run(self):
        while not self.parar.is_set():
            m, s = ler_meminfo(), ler_status_proc()
            self.rss_max = max(self.rss_max, s.get("VmRSS", 0))
            av = m.get("MemAvailable", 0)
            self.memavail_min = av if self.memavail_min is None else min(self.memavail_min, av)
            self.swap_max = max(self.swap_max, m.get("SwapTotal", 0) - m.get("SwapFree", 0))
            self.cache_max = max(self.cache_max, m.get("Cached", 0))
            self.parar.wait(self.intervalo)


# ----------------------------------------------------------------------------
# Configuração de uma execução
# ----------------------------------------------------------------------------
@dataclass
class Config:
    id: str = "exec"
    indice: str = "dados/indice_pequeno"
    indice_fallback: str = ""
    saida: str = "resultados/brutos"
    log: str = ""
    usar_mmap: bool = False
    frio: bool = True                 # começa com cache de páginas do índice limpo
    workers: int = 2
    produtores: int = 2
    fila_capacidade: int = 16
    put_timeout: float = 0.0          # 0 = put bloqueante; >0 = timeout em segundos
    put_retentativas: int = 0
    intervalo_ms: float = 0.0         # intervalo entre envios de cada produtor
    n_req: int = 300
    n_unicas: int = 100
    carga: str = "repetidas"          # repetidas | distintas
    cache_capacidade: int = 128       # 0 desativa o cache
    cache_politica: str = "lru"       # lru | fifo
    top_k: int = 5
    max_chars: int = 4000             # limite do contexto (aprox. tokens = chars/4)
    gerador: str = "simulado"         # simulado | cpu | ollama
    ger_base_ms: float = 20.0
    ger_ms_por_mil_chars: float = 10.0
    taxa_falha: float = 0.0           # falha injetada no serviço de geração
    retentativas: int = 2
    ollama_url: str = "http://localhost:11434"
    modelo: str = "phi4-mini"
    num_predict: int = 32
    timeout_ger: float = 120.0
    limite_mem_extra_mb: int = 0      # 0 = sem limite; >0 aplica RLIMIT_DATA = VmData atual + extra (memória anônima)
    semente: int = 7
    log_flush_cada: int = 50


class ArquivoAusente(Exception):
    pass


class IndiceIndisponivel(Exception):
    pass


# ----------------------------------------------------------------------------
# Embeddings simulados (hashing trick) e fragmentação
# ----------------------------------------------------------------------------
_hash_cache = {}


def embed_tokens(tokens, dim=DIM):
    idx, sinal = [], []
    for t in tokens:
        h = _hash_cache.get(t)
        if h is None:
            c = zlib.crc32(t.encode("utf-8"))
            h = (c % dim, 1.0 if (c >> 31) & 1 else -1.0)
            _hash_cache[t] = h
        idx.append(h[0])
        sinal.append(h[1])
    v = np.bincount(np.array(idx, dtype=np.intp), weights=sinal, minlength=dim).astype(np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def montar_contexto(trechos, max_chars):
    partes, total = [], 0
    for t in trechos:
        if partes and total + len(t) > max_chars:
            break
        partes.append(t)
        total += len(t) + 1
    return "\n".join(partes)[:max_chars], len(partes)


# ----------------------------------------------------------------------------
# Ingestão e índice
# ----------------------------------------------------------------------------
def ingerir(corpus_dir, indice_dir, chunk_palavras=100, log=None):
    """Lê .txt, fragmenta em trechos de `chunk_palavras` palavras, gera vetores e grava:
       vetores.npy (float32 n x DIM), chunks.bin (texto), offsets.npy (offset,len), meta.json."""
    t_ini = time.perf_counter()
    corpus_dir, indice_dir = Path(corpus_dir), Path(indice_dir)
    arquivos = sorted(corpus_dir.glob("*.txt"))
    if not arquivos:
        raise ArquivoAusente(f"nenhum .txt em {corpus_dir}")
    indice_dir.mkdir(parents=True, exist_ok=True)
    io0 = ler_io_proc()
    t_leit = t_frag = t_emb = 0.0
    bytes_corpus = 0
    blocos, bloco_atual, offsets, nomes = [], [], [], []
    pos = 0
    t_grav0 = time.perf_counter()
    with open(indice_dir / "chunks.bin", "wb") as fc:
        for arq in arquivos:
            t0 = time.perf_counter()
            with open(arq, "rb") as f:
                dados = f.read()
            t_leit += time.perf_counter() - t0
            bytes_corpus += len(dados)
            t0 = time.perf_counter()
            palavras = dados.decode("utf-8").split()
            trechos = [palavras[j:j + chunk_palavras]
                       for j in range(0, len(palavras), chunk_palavras)]
            t_frag += time.perf_counter() - t0
            nomes.append(arq.name)
            for tk in trechos:
                t0 = time.perf_counter()
                bloco_atual.append(embed_tokens(tk))
                t_emb += time.perf_counter() - t0
                b = " ".join(tk).encode("utf-8")
                fc.write(b)
                offsets.append((pos, len(b)))
                pos += len(b)
                if len(bloco_atual) >= 4096:
                    blocos.append(np.stack(bloco_atual))
                    bloco_atual = []
            if log:
                log.escrever("ingestao_doc", arquivo=arq.name, trechos=len(trechos))
    if bloco_atual:
        blocos.append(np.stack(bloco_atual))
    vetores = np.concatenate(blocos).astype(np.float32)
    np.save(indice_dir / "vetores.npy", vetores)
    np.save(indice_dir / "offsets.npy", np.array(offsets, dtype=np.int64))
    meta = {"n_chunks": int(vetores.shape[0]), "dim": DIM,
            "chunk_palavras": chunk_palavras, "n_docs": len(arquivos)}
    (indice_dir / "meta.json").write_text(json.dumps(meta))
    t_grav = time.perf_counter() - t_grav0 - t_leit - t_frag - t_emb
    io1 = ler_io_proc()
    res = {
        "corpus": str(corpus_dir), "indice": str(indice_dir), **meta,
        "bytes_corpus": bytes_corpus,
        "bytes_vetores": (indice_dir / "vetores.npy").stat().st_size,
        "bytes_chunks": (indice_dir / "chunks.bin").stat().st_size,
        "bytes_indice": sum((indice_dir / n).stat().st_size for n in
                            ("vetores.npy", "chunks.bin", "offsets.npy", "meta.json")),
        "t_leitura_s": round(t_leit, 3), "t_fragmentacao_s": round(t_frag, 3),
        "t_embeddings_s": round(t_emb, 3), "t_gravacao_s": round(max(t_grav, 0), 3),
        "t_total_s": round(time.perf_counter() - t_ini, 3),
        "io_rchar": io1.get("rchar", 0) - io0.get("rchar", 0),
        "io_wchar": io1.get("wchar", 0) - io0.get("wchar", 0),
        "io_read_bytes": io1.get("read_bytes", 0) - io0.get("read_bytes", 0),
        "io_write_bytes": io1.get("write_bytes", 0) - io0.get("write_bytes", 0),
    }
    (indice_dir / "ingestao.json").write_text(json.dumps(res, indent=2))
    if log:
        log.escrever("ingestao_fim", **{k: res[k] for k in ("n_docs", "n_chunks", "t_total_s")})
    return res


class Indice:
    """Índice vetorial em arquivos. `usar_mmap` alterna entre leitura convencional
    (np.load + os.pread) e arquivos mapeados em memória (np.load mmap_mode + mmap)."""

    def __init__(self, pasta, usar_mmap=False):
        self.pasta, self.usar_mmap = Path(pasta), usar_mmap
        self._fd = None
        self._mm = None

    def arquivos(self):
        return [self.pasta / n for n in ("vetores.npy", "chunks.bin", "offsets.npy", "meta.json")]

    def esvaziar_cache_paginas(self):
        for p in self.arquivos():
            fadvise_dontneed(p)

    def carregar(self):
        for p in self.arquivos():
            if not p.exists():
                raise ArquivoAusente(str(p))
        try:
            self.meta = json.loads((self.pasta / "meta.json").read_text())
            vet = np.load(self.pasta / "vetores.npy", mmap_mode="r" if self.usar_mmap else None)
            self.vetores = np.asarray(vet)
            self.offsets = np.load(self.pasta / "offsets.npy")
            self._fd = os.open(str(self.pasta / "chunks.bin"), os.O_RDONLY)
            if self.usar_mmap:
                self._mm = mmap.mmap(self._fd, 0, access=mmap.ACCESS_READ)
        except (MemoryError, OSError, ValueError) as e:
            raise IndiceIndisponivel(f"falha ao carregar índice: {e!r}") from e
        self.n = self.vetores.shape[0]

    def buscar(self, q, k):
        scores = self.vetores @ q
        k = min(k, self.n)
        idx = np.argpartition(scores, -k)[-k:]
        idx = idx[np.argsort(scores[idx])[::-1]]
        return idx, scores[idx]

    def ler_trecho(self, i):
        off, ln = int(self.offsets[i][0]), int(self.offsets[i][1])
        b = self._mm[off:off + ln] if self.usar_mmap else os.pread(self._fd, ln, off)
        return b.decode("utf-8")

    def ler_trechos(self, ids):
        return [self.ler_trecho(i) for i in ids]

    def fechar(self):
        try:
            if self._mm is not None:
                self._mm.close()
            if self._fd is not None:
                os.close(self._fd)
        except (OSError, ValueError, BufferError):
            pass


# ----------------------------------------------------------------------------
# Log com escrita concorrente protegida
# ----------------------------------------------------------------------------
LINHA_OK = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3} \S+ \S+ \{.*\}$")


class LogSeguro:
    """Uma linha por evento. seguro=True usa mutex (a linha inteira é gravada de forma
    atômica). seguro=False existe só para demonstrar log intercalado (sincronizacao.py)."""

    def __init__(self, caminho, flush_cada=50, seguro=True):
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self.f = open(caminho, "w", encoding="utf-8")
        self.lock = threading.Lock()
        self.seguro, self.flush_cada, self.n = seguro, flush_cada, 0

    def escrever(self, evento, **campos):
        ts = datetime.now().isoformat(timespec="milliseconds")
        nome = threading.current_thread().name.replace(" ", "_")
        carga = json.dumps(campos, ensure_ascii=False, separators=(",", ":"))
        if self.seguro:
            linha = f"{ts} {nome} {evento} {carga}\n"
            with self.lock:
                self.f.write(linha)
                self.n += 1
                if self.n % self.flush_cada == 0:
                    self.f.flush()
        else:
            self.f.write(f"{ts} {nome} ")
            time.sleep(0)  # cede a CPU no meio da linha -> intercalação
            self.f.write(f"{evento} {carga}\n")

    def fechar(self):
        with self.lock:
            self.f.flush()
            self.f.close()


def validar_log(caminho):
    total = ruins = 0
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            total += 1
            if not LINHA_OK.match(linha.rstrip("\n")):
                ruins += 1
    return total, ruins


# ----------------------------------------------------------------------------
# Cache compartilhado
# ----------------------------------------------------------------------------
class CacheCompartilhado:
    """Cache LRU/FIFO protegido por mutex. Mede acertos, erros, substituições,
    duplicações (put de chave que já existia) e tempo economizado."""

    def __init__(self, capacidade, politica="lru"):
        self.capacidade, self.politica = capacidade, politica
        self.d = OrderedDict()
        self.lock = threading.Lock()
        self.acertos = self.erros = self.evicoes = self.duplicados = 0
        self.tempo_economizado = 0.0

    def get(self, chave):
        with self.lock:
            if self.capacidade > 0 and chave in self.d:
                valor, custo = self.d[chave]
                if self.politica == "lru":
                    self.d.move_to_end(chave)
                self.acertos += 1
                self.tempo_economizado += custo
                return valor
            self.erros += 1
            return None

    def put(self, chave, valor, custo):
        if self.capacidade <= 0:
            return
        with self.lock:
            if chave in self.d:
                self.duplicados += 1
                self.d[chave] = (valor, custo)
                return
            self.d[chave] = (valor, custo)
            while len(self.d) > self.capacidade:
                self.d.popitem(last=False)
                self.evicoes += 1

    def stats(self):
        with self.lock:
            tot = self.acertos + self.erros
            return {"cache_acertos": self.acertos, "cache_erros": self.erros,
                    "cache_taxa_acerto": round(self.acertos / tot, 4) if tot else 0.0,
                    "cache_tamanho_final": len(self.d), "cache_evicoes": self.evicoes,
                    "cache_duplicados": self.duplicados,
                    "cache_tempo_economizado_s": round(self.tempo_economizado, 3)}


# ----------------------------------------------------------------------------
# Geração (simulada, CPU ou Ollama) com retentativas
# ----------------------------------------------------------------------------
class FalhaServico(Exception):
    pass


class Gerador:
    def __init__(self, cfg):
        self.cfg = cfg
        self.rng = random.Random(cfg.semente)

    def _chamar(self, consulta, contexto):
        c = self.cfg
        if c.gerador == "ollama":
            return self._ollama(consulta, contexto)
        if c.taxa_falha > 0 and self.rng.random() < c.taxa_falha:
            raise FalhaServico("falha injetada no serviço de geração")
        dur = (c.ger_base_ms + c.ger_ms_por_mil_chars * len(contexto) / 1000.0) / 1000.0
        if c.gerador == "simulado":
            time.sleep(dur)               # espera, como uma E/S ou uma GPU remota
        else:                             # "cpu": ocupa a CPU (segura a GIL)
            fim = time.perf_counter() + dur
            while time.perf_counter() < fim:
                pass
        return f"[{c.gerador}] resposta simulada ({len(contexto)} chars de contexto)"

    def _ollama(self, consulta, contexto):
        c = self.cfg
        prompt = (f"Contexto:\n{contexto}\n\nPergunta: {consulta}\n"
                  "Responda em uma frase curta.")
        corpo = json.dumps({"model": c.modelo, "prompt": prompt, "stream": False,
                            "options": {"num_predict": c.num_predict, "temperature": 0}}).encode()
        req = urllib.request.Request(c.ollama_url.rstrip("/") + "/api/generate", data=corpo,
                                     headers={"Content-Type": "application/json"})
        # opener sem proxy: o Ollama é local e variáveis HTTP(S)_PROXY não devem interferir
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=c.timeout_ger) as r:
            dados = json.load(r)
        return dados.get("response", "").strip().replace("\n", " ")[:160]

    def gerar(self, consulta, contexto):
        tentativas = 0
        while True:
            tentativas += 1
            try:
                return self._chamar(consulta, contexto), {"tentativas": tentativas, "falhou": False}
            except (FalhaServico, OSError, ValueError) as e:  # URLError/Timeout herdam de OSError
                if tentativas > self.cfg.retentativas:
                    return ("[serviço indisponível: resposta degradada]",
                            {"tentativas": tentativas, "falhou": True, "erro": str(e)[:80]})
                time.sleep(0.05 * tentativas)


# ----------------------------------------------------------------------------
# Servidor: produtores -> fila limitada -> workers
# ----------------------------------------------------------------------------
class Servidor:
    def __init__(self, cfg, indice, log):
        self.cfg, self.indice, self.log = cfg, indice, log
        self.cache = CacheCompartilhado(cfg.cache_capacidade, cfg.cache_politica)
        self.gerador = Gerador(cfg)
        self.fila = queue.Queue(maxsize=max(1, cfg.fila_capacidade))
        self.regs = [[] for _ in range(cfg.workers)]       # registros por worker (sem contenção)
        self.ocupado = [0.0] * cfg.workers
        self.amostras_fila = [[] for _ in range(cfg.produtores)]
        self.enviadas = [0] * cfg.produtores
        self.rejeitadas = [0] * cfg.produtores
        self.retent_put = [0] * cfg.produtores
        self.tempo_total = 0.0

    # --- pipeline de uma requisição ---
    def processar(self, rid, texto):
        c = self.cfg
        chave = " ".join(texto.lower().split())
        self.log.escrever("consulta", req=rid)
        v = self.cache.get(chave)
        if v is not None:
            self.log.escrever("cache_hit", req=rid)
            return {"hit": True, "t_rec": 0.0, "t_ger": 0.0, "n_trechos": v["n_trechos"],
                    "bytes_ctx": v["bytes_ctx"], "falha": False}
        self.log.escrever("cache_miss", req=rid)
        t0 = time.perf_counter()
        q = embed_tokens(chave.split())
        ids, _ = self.indice.buscar(q, c.top_k)
        contexto, n_tr = montar_contexto(self.indice.ler_trechos(ids), c.max_chars)
        t_rec = time.perf_counter() - t0
        self.log.escrever("recuperacao", req=rid, trechos=n_tr, bytes=len(contexto),
                          tokens_aprox=len(contexto) // 4, ms=round(t_rec * 1000, 2))
        t1 = time.perf_counter()
        resposta, info = self.gerador.gerar(texto, contexto)
        t_ger = time.perf_counter() - t1
        self.log.escrever("geracao", req=rid, ms=round(t_ger * 1000, 2),
                          tentativas=info["tentativas"], falhou=info["falhou"],
                          resumo=resposta[:60])
        if info["falhou"]:
            self.log.escrever("falha", req=rid, origem="geracao", erro=info.get("erro", ""))
        else:
            self.cache.put(chave, {"n_trechos": n_tr, "bytes_ctx": len(contexto)}, t_rec + t_ger)
        return {"hit": False, "t_rec": t_rec, "t_ger": t_ger, "n_trechos": n_tr,
                "bytes_ctx": len(contexto), "falha": info["falhou"],
                "tentativas": info["tentativas"]}

    # --- threads ---
    def produtor(self, pid, itens):
        c = self.cfg
        for rid, texto in itens:
            if c.intervalo_ms > 0:
                time.sleep(c.intervalo_ms / 1000.0)
            item = (rid, texto, time.perf_counter())
            tentativas = 0
            while True:
                try:
                    if c.put_timeout > 0:
                        self.fila.put(item, timeout=c.put_timeout)
                    else:
                        self.fila.put(item)          # bloqueia: contrapressão
                    self.enviadas[pid] += 1
                    self.amostras_fila[pid].append(self.fila.qsize())
                    break
                except queue.Full:
                    if tentativas >= c.put_retentativas:
                        self.rejeitadas[pid] += 1
                        self.log.escrever("fila_cheia_rejeitada", req=rid)
                        break
                    tentativas += 1
                    self.retent_put[pid] += 1
                    self.log.escrever("fila_cheia_retentativa", req=rid, tentativa=tentativas)

    def consumidor(self, wid):
        regs = self.regs[wid]
        while True:
            item = self.fila.get()                  # bloqueia se a fila estiver vazia
            if item is None:
                self.fila.task_done()
                break
            rid, texto, t_enf = item
            t_ini = time.perf_counter()
            try:
                reg = self.processar(rid, texto)
            except Exception as e:                  # falha isolada: o worker continua vivo
                self.log.escrever("falha", req=rid, origem="worker", erro=repr(e)[:100])
                reg = {"hit": False, "t_rec": 0.0, "t_ger": 0.0, "n_trechos": 0,
                       "bytes_ctx": 0, "falha": True}
            t_fim = time.perf_counter()
            self.ocupado[wid] += t_fim - t_ini
            reg.update(rid=rid, espera=t_ini - t_enf, lat=t_fim - t_enf, t_fim=t_fim, worker=wid)
            regs.append(reg)
            self.fila.task_done()

    def executar(self, carga):
        c = self.cfg
        itens = list(enumerate(carga))
        cons = [threading.Thread(target=self.consumidor, args=(i,), name=f"worker-{i}")
                for i in range(c.workers)]
        prod = [threading.Thread(target=self.produtor, args=(p, itens[p::c.produtores]),
                                 name=f"produtor-{p}") for p in range(c.produtores)]
        t0 = time.perf_counter()
        for t in cons + prod:
            t.start()
        for t in prod:
            t.join()
        for _ in cons:
            self.fila.put(None)                     # "pílula de veneno": encerra cada worker
        for t in cons:
            t.join()
        self.tempo_total = time.perf_counter() - t0
        return len(itens)


def _pct(v, p):
    return float(np.percentile(v, p)) if len(v) else 0.0


def resumir(srv, n_total):
    c = srv.cfg
    regs = [r for rs in srv.regs for r in rs]
    lat = [r["lat"] * 1000 for r in regs]
    esp = [r["espera"] * 1000 for r in regs]
    rec = [r["t_rec"] * 1000 for r in regs if not r["hit"]]
    ger = [r["t_ger"] * 1000 for r in regs if not r["hit"]]
    serv = [(r["lat"] - r["espera"]) * 1000 for r in regs]
    amostras = [a for l in srv.amostras_fila for a in l]
    enviadas = sum(srv.enviadas)
    ids = [r["rid"] for r in sorted(regs, key=lambda r: r["t_fim"])]
    desordem = sum(1 for i in range(1, len(ids)) if ids[i] < ids[i - 1])
    tt = srv.tempo_total or 1e-9
    return {
        "n_enviadas": enviadas, "n_processadas": len(regs), "n_rejeitadas": sum(srv.rejeitadas),
        "n_retentativas_fila": sum(srv.retent_put),
        "n_falhas": sum(1 for r in regs if r["falha"]),
        "tempo_total_s": round(srv.tempo_total, 4),
        "vazao_req_s": round(len(regs) / tt, 2),
        "lat_media_ms": round(float(np.mean(lat)), 2) if lat else 0.0,
        "lat_mediana_ms": round(_pct(lat, 50), 2), "lat_p95_ms": round(_pct(lat, 95), 2),
        "servico_media_ms": round(float(np.mean(serv)), 2) if serv else 0.0,
        "espera_fila_media_ms": round(float(np.mean(esp)), 2) if esp else 0.0,
        "espera_fila_p95_ms": round(_pct(esp, 95), 2),
        "t_recuperacao_media_ms": round(float(np.mean(rec)), 3) if rec else 0.0,
        "t_recuperacao_p95_ms": round(_pct(rec, 95), 3),
        "t_resposta_media_ms": round(float(np.mean(ger)), 3) if ger else 0.0,
        "t_resposta_p95_ms": round(_pct(ger, 95), 3),
        "fila_media": round(float(np.mean(amostras)), 2) if amostras else 0.0,
        "fila_max": int(max(amostras)) if amostras else 0,
        "utilizacao_workers": round(sum(srv.ocupado) / (c.workers * tt), 3),
        "trechos_medio": round(float(np.mean([r["n_trechos"] for r in regs])), 2) if regs else 0.0,
        "bytes_contexto_medio": round(float(np.mean([r["bytes_ctx"] for r in regs])), 1) if regs else 0.0,
        "perdidos": enviadas - len(regs),
        "duplicados": len(ids) - len(set(ids)),
        "desordem_adjacente": desordem,
        **srv.cache.stats(),
    }


def commit_git():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ,
                              capture_output=True, text=True, timeout=5).stdout.strip() or "n/a"
    except Exception:
        return "n/a"


def executar(cfg):
    """Uma execução completa (idealmente em processo próprio). Retorna o resumo."""
    saida = Path(cfg.saida)
    saida.mkdir(parents=True, exist_ok=True)
    log = LogSeguro(cfg.log or (saida / f"{cfg.id}.log"), cfg.log_flush_cada)
    log.escrever("inicio", id=cfg.id, workers=cfg.workers, produtores=cfg.produtores,
                 mmap=cfg.usar_mmap, n_req=cfg.n_req, indice=cfg.indice)
    f0 = foto()
    status, erro = "ok", ""
    indice_usado = cfg.indice
    if cfg.limite_mem_extra_mb > 0:
        # RLIMIT_DATA limita memória anônima/privada (heap, np.load convencional, pilhas).
        # Arquivos mapeados somente-leitura (mmap) NÃO contam: o índice em mmap continua cabendo.
        usado = f0["status"]["VmData"] * 1024
        _, hard = resource.getrlimit(resource.RLIMIT_DATA)
        resource.setrlimit(resource.RLIMIT_DATA, (usado + cfg.limite_mem_extra_mb * 1048576, hard))
        log.escrever("limite_memoria", extra_mb=cfg.limite_mem_extra_mb)

    def tentar(pasta):
        ind = Indice(pasta, cfg.usar_mmap)
        if cfg.frio and ind.pasta.exists():
            ind.esvaziar_cache_paginas()
        ind.carregar()
        return ind

    t_carga0 = time.perf_counter()
    indice = None
    try:
        indice = tentar(cfg.indice)
    except (ArquivoAusente, IndiceIndisponivel) as e:
        erro = f"{type(e).__name__}: {e}"
        log.escrever("falha", origem="indice", erro=erro[:150])
        if cfg.indice_fallback:
            try:
                indice = tentar(cfg.indice_fallback)
                status, indice_usado = "recuperado_com_fallback", cfg.indice_fallback
                log.escrever("recuperacao_falha", fallback=cfg.indice_fallback)
            except (ArquivoAusente, IndiceIndisponivel) as e2:
                erro += f" | fallback: {e2}"
        if indice is None:
            status = "falha_controlada"
    t_carga = time.perf_counter() - t_carga0
    f1 = foto()

    resumo = {}
    if indice is not None:
        mon = Monitor()
        mon.start()
        srv = Servidor(cfg, indice, log)
        carga = montar_carga(cfg.n_req, cfg.n_unicas, cfg.semente, cfg.carga)
        try:
            n_total = srv.executar(carga)
            resumo = resumir(srv, n_total)
        except Exception as e:
            status, erro = "falha_controlada", repr(e)[:150]
            log.escrever("falha", origem="servidor", erro=erro)
        mon.parar.set()
        mon.join()
        indice_tam_mb = sum(p.stat().st_size for p in indice.arquivos()) / 1e6
        indice.fechar()
    else:
        mon = None
        indice_tam_mb = 0.0

    f2 = foto()
    log.escrever("encerramento", status=status)
    log.fechar()
    linhas, ruins = validar_log(log.f.name)

    def d(a, b, k1, k2):
        return b[k1].get(k2, 0) - a[k1].get(k2, 0)

    s0, s1, s2 = f0["status"], f1["status"], f2["status"]
    dur_exec = f2["t"] - f1["t"]
    ops = d(f1, f2, "io", "syscr") + d(f1, f2, "io", "syscw")
    mi = f2["meminfo"]
    out = {
        "id": cfg.id, "status": status, "erro": erro, "indice_usado": indice_usado,
        "inicio": datetime.now().isoformat(timespec="seconds"), "commit": commit_git(),
        "python": sys.version.split()[0], "numpy": np.__version__, "kernel": os.uname().release,
        **asdict(cfg),
        "tamanho_indice_mb": round(indice_tam_mb, 2), "t_carga_indice_s": round(t_carga, 4),
        **resumo,
        "rss_base_mb": mb(s0.get("VmRSS", 0)), "rss_apos_carga_mb": mb(s1.get("VmRSS", 0)),
        "rss_pico_mb": mb(s2.get("VmHWM", 0)), "rss_fim_mb": mb(s2.get("VmRSS", 0)),
        "rss_file_fim_mb": mb(s2.get("RssFile", 0)), "rss_anon_fim_mb": mb(s2.get("RssAnon", 0)),
        "vsz_base_mb": mb(s0.get("VmSize", 0)), "vsz_pico_mb": mb(s2.get("VmPeak", 0)),
        "memavail_inicio_mb": mb(f0["meminfo"].get("MemAvailable", 0)),
        "memavail_min_mb": mb(mon.memavail_min) if mon and mon.memavail_min else 0,
        "swap_usado_max_mb": mb(mon.swap_max) if mon else 0,
        "cache_paginas_fim_mb": mb(mi.get("Cached", 0)),
        "faltas_menores_exec": f2["minflt"] - f1["minflt"],
        "faltas_maiores_exec": f2["majflt"] - f1["majflt"],
        "faltas_menores_total": f2["minflt"] - f0["minflt"],
        "faltas_maiores_total": f2["majflt"] - f0["majflt"],
        "sys_pgmajfault": d(f0, f2, "vmstat", "pgmajfault"),
        "sys_pswpin": d(f0, f2, "vmstat", "pswpin"), "sys_pswpout": d(f0, f2, "vmstat", "pswpout"),
        "io_read_mb": round(d(f0, f2, "io", "read_bytes") / 1e6, 2),
        "io_write_mb": round(d(f0, f2, "io", "write_bytes") / 1e6, 3),
        "io_rchar_mb": round(d(f0, f2, "io", "rchar") / 1e6, 2),
        "io_wchar_mb": round(d(f0, f2, "io", "wchar") / 1e6, 3),
        "io_ops_s": round(ops / dur_exec, 1) if dur_exec > 0 else 0,
        "threads_pico": s2.get("Threads", 0),
        "log_linhas": linhas, "log_corrompidas": ruins,
    }
    (saida / f"{cfg.id}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out


def _parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("ingerir")
    pi.add_argument("--corpus", required=True)
    pi.add_argument("--indice", required=True)
    pi.add_argument("--chunk-palavras", type=int, default=100)
    pi.add_argument("--log", default="")
    pe = sub.add_parser("executar")
    pe.add_argument("--config-json", default="", help="JSON com valores que sobrescrevem as flags")
    padrao = Config()
    for f in fields(Config):
        valor = getattr(padrao, f.name)
        flag = "--" + f.name.replace("_", "-")
        if isinstance(valor, bool):
            pe.add_argument(flag, action=argparse.BooleanOptionalAction, default=valor)
        else:
            pe.add_argument(flag, type=type(valor), default=valor)
    return ap


def main():
    a = _parser().parse_args()
    if a.cmd == "ingerir":
        log = LogSeguro(a.log) if a.log else None
        r = ingerir(a.corpus, a.indice, a.chunk_palavras, log)
        if log:
            log.fechar()
        print(json.dumps(r, indent=2))
        return
    valores = {f.name: getattr(a, f.name) for f in fields(Config)}
    if a.config_json:
        valores.update(json.loads(a.config_json))
    r = executar(Config(**valores))
    print(f"[{r['id']}] status={r['status']} req={r.get('n_processadas', 0)} "
          f"vazao={r.get('vazao_req_s', 0)} req/s p95={r.get('lat_p95_ms', 0)} ms "
          f"acerto_cache={r.get('cache_taxa_acerto', 0)} rss_pico={r['rss_pico_mb']} MB")


if __name__ == "__main__":
    main()
