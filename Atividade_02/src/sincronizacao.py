#!/usr/bin/env python3
"""Parte D: sincronização obrigatória, com falhas CONTROLADAS e a correção de cada uma.

Demonstrações (cada uma repetida --reps vezes):
  1. cache_compartilhado  : sem lock x lock global x lock curto
                            -> atualização perdida e duplicação de trabalho
  2. log_concorrente      : escrita sem mutex x com mutex -> log intercalado
  3. buffer_limitado      : produtores/consumidores com empty/full/mutex
                            sem mutex -> itens perdidos/duplicados; com mutex -> correto
                            + consumidor bloqueado (fila vazia) resolvido com timeout
  4. deadlock             : espera circular real em PROCESSO ISOLADO (encerrado por timeout)
                            e a versão com timeout + ordenação de locks (recuperação)

Nota honesta sobre o CPython: a GIL torna cada operação isolada de dict/lista atômica,
mas sequências "verificar e depois agir" e "ler-modificar-escrever" continuam NÃO sendo
atômicas. Para tornar a corrida reprodutível, cedemos a CPU (time.sleep(0)) no meio
dessas sequências e diminuímos o intervalo de troca de threads.

Uso: python src/sincronizacao.py --reps 3
"""
import argparse
import csv
import json
import multiprocessing as mp
import random
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from genresearch import LogSeguro, validar_log  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- 1. cache
class CacheDemo:
    def __init__(self, variante, custo_s=0.005):
        self.v, self.custo = variante, custo_s
        self.d = {}
        self.lock = threading.Lock()
        self.acertos = self.erros = self.computacoes = 0   # contadores COMPARTILHADOS

    def _inc(self, nome):
        """Incremento ler-modificar-escrever (não atômico)."""
        tmp = getattr(self, nome)
        time.sleep(0)                  # outra thread pode entrar aqui
        setattr(self, nome, tmp + 1)

    def obter(self, k):
        """Retorna (acerto?, computou?) - verdade local da thread, sem compartilhar."""
        if self.v == "sem_lock":
            if k in self.d:
                self._inc("acertos")
                return True, False
            self._inc("erros")
            time.sleep(self.custo)     # computar o valor (recuperação + geração)
            self.d[k] = k * 2
            self._inc("computacoes")
            return False, True
        if self.v == "lock_global":    # tudo dentro do mutex, inclusive a computação
            with self.lock:
                if k in self.d:
                    self._inc("acertos")
                    return True, False
                self._inc("erros")
                time.sleep(self.custo)
                self.d[k] = k * 2
                self._inc("computacoes")
                return False, True
        # lock_curto: mutex só em volta das seções críticas; computa FORA do lock
        with self.lock:
            if k in self.d:
                self._inc("acertos")
                return True, False
            self._inc("erros")
        time.sleep(self.custo)
        with self.lock:
            self._inc("computacoes")
            self.d.setdefault(k, k * 2)
        return False, True


def demo_cache(variante, n_threads=8, ops=300, chaves=20):
    cache = CacheDemo(variante)
    verdade = []                       # (acertos, computacoes) por thread

    def trabalho(seed):
        rnd = random.Random(seed)
        a = c = 0
        for _ in range(ops):
            hit, comp = cache.obter(rnd.randrange(chaves))
            a += hit
            c += comp
        verdade.append((a, c))

    ths = [threading.Thread(target=trabalho, args=(i,)) for i in range(n_threads)]
    t0 = time.perf_counter()
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    dt = time.perf_counter() - t0
    esperadas = n_threads * ops
    reg = cache.acertos + cache.erros
    comp_reais = sum(c for _, c in verdade)
    return {"tempo_s": round(dt, 3), "ops_esperadas": esperadas, "ops_registradas": reg,
            "atualizacoes_perdidas": esperadas - reg,
            "acertos_reais": sum(a for a, _ in verdade), "acertos_registrados": cache.acertos,
            "computacoes_reais": comp_reais, "chaves_unicas": len(cache.d),
            "computacoes_redundantes": comp_reais - len(cache.d)}


# ------------------------------------------------------------------- 2. log
def demo_log(seguro, n_threads=4, linhas=300):
    caminho = RAIZ / "resultados" / "logs" / f"demo_log_{'com' if seguro else 'sem'}_mutex.log"
    log = LogSeguro(caminho, flush_cada=10, seguro=seguro)

    def trabalho(i):
        for j in range(linhas):
            log.escrever("evento", thread=i, seq=j)

    ths = [threading.Thread(target=trabalho, args=(i,), name=f"t{i}") for i in range(n_threads)]
    t0 = time.perf_counter()
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    dt = time.perf_counter() - t0
    log.fechar()
    total, ruins = validar_log(caminho)
    return {"tempo_s": round(dt, 3), "linhas_esperadas": n_threads * linhas,
            "linhas_no_arquivo": total, "linhas_corrompidas": ruins}


# ------------------------------------------------------- 3. buffer limitado
class BufferLimitado:
    """Buffer circular. empty = vagas livres, full = itens prontos, mutex = posições."""

    def __init__(self, capacidade, usar_mutex=True):
        self.cap, self.usar_mutex = capacidade, usar_mutex
        self.buf = [None] * capacidade
        self.entra = self.sai = self.n = 0
        self.max_ocupacao = 0
        self.empty = threading.Semaphore(capacidade)
        self.full = threading.Semaphore(0)
        self.mutex = threading.Lock()

    def produzir(self, item):
        self.empty.acquire()
        if self.usar_mutex:
            with self.mutex:
                self._inserir(item)
        else:
            self._inserir(item)
        self.full.release()

    def _inserir(self, item):
        i = self.entra
        time.sleep(0)
        self.buf[i] = item
        time.sleep(0)
        self.entra = (i + 1) % self.cap
        self.n += 1
        self.max_ocupacao = max(self.max_ocupacao, self.n)

    def consumir(self, timeout=None):
        if not self.full.acquire(timeout=timeout):
            raise TimeoutError("buffer vazio: consumidor bloqueado até o timeout")
        if self.usar_mutex:
            with self.mutex:
                item = self._retirar()
        else:
            item = self._retirar()
        self.empty.release()
        return item

    def _retirar(self):
        i = self.sai
        time.sleep(0)
        item = self.buf[i]
        self.buf[i] = None
        time.sleep(0)
        self.sai = (i + 1) % self.cap
        self.n -= 1
        return item


def demo_buffer(usar_mutex, produtores=2, consumidores=2, por_produtor=400, capacidade=8):
    b = BufferLimitado(capacidade, usar_mutex)
    consumidos = [[] for _ in range(consumidores)]
    total = produtores * por_produtor
    por_consumidor = total // consumidores

    def prod(p):
        for j in range(por_produtor):
            b.produzir(p * 100000 + j)

    def cons(c):
        for _ in range(por_consumidor):
            consumidos[c].append(b.consumir())

    ths = ([threading.Thread(target=prod, args=(p,)) for p in range(produtores)] +
           [threading.Thread(target=cons, args=(c,)) for c in range(consumidores)])
    t0 = time.perf_counter()
    for t in ths:
        t.start()
    for t in ths:
        t.join(timeout=30)
    dt = time.perf_counter() - t0
    todos = [x for l in consumidos for x in l]
    esperados = {p * 100000 + j for p in range(produtores) for j in range(por_produtor)}
    validos = [x for x in todos if x is not None]
    return {"tempo_s": round(dt, 3), "itens_produzidos": total, "itens_consumidos": len(validos),
            "itens_perdidos": len(esperados - set(validos)),
            "itens_duplicados": len(validos) - len(set(validos)),
            "leituras_de_slot_vazio": len(todos) - len(validos),
            "max_ocupacao": b.max_ocupacao, "capacidade": capacidade,
            "ocupacao_dentro_do_limite": b.max_ocupacao <= capacidade}


def demo_consumidor_bloqueado(timeout=0.3):
    b = BufferLimitado(4)
    t0 = time.perf_counter()
    try:
        b.consumir(timeout=timeout)
        bloqueou = False
    except TimeoutError:
        bloqueou = True
    return {"consumidor_bloqueado_ate_timeout": bloqueou,
            "tempo_bloqueado_s": round(time.perf_counter() - t0, 3)}


# --------------------------------------------------------------- 4. deadlock
def _deadlock_filho():
    """Executa em PROCESSO ISOLADO: duas threads, locks em ordem oposta -> espera circular."""
    A, B = threading.Lock(), threading.Lock()

    def t1():
        with A:
            print("[filho] t1 segura A, quer B", flush=True)
            time.sleep(0.2)
            with B:
                pass

    def t2():
        with B:
            print("[filho] t2 segura B, quer A", flush=True)
            time.sleep(0.2)
            with A:
                pass

    ths = [threading.Thread(target=t1, daemon=True), threading.Thread(target=t2, daemon=True)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    print("[filho] terminou sem deadlock (inesperado)", flush=True)


def demo_deadlock_real(espera=3.0):
    ctx = mp.get_context("spawn")
    p = ctx.Process(target=_deadlock_filho)
    t0 = time.perf_counter()
    p.start()
    p.join(espera)
    travado = p.is_alive()
    if travado:
        print(f"[pai] processo {p.pid} travado após {espera}s: deadlock confirmado; encerrando (terminate)", flush=True)
        p.terminate()
        p.join(2)
        if p.is_alive():
            p.kill()
            p.join()
    return {"deadlock_confirmado": travado, "processo_encerrado_pelo_pai": travado,
            "tempo_s": round(time.perf_counter() - t0, 3), "exitcode_filho": p.exitcode}


def demo_deadlock_recuperavel(timeout=0.5):
    """Mesma ordem oposta, mas com acquire(timeout): detecta, libera, e refaz na ordem A->B."""
    A, B = threading.Lock(), threading.Lock()
    stats = {"detectados": 0, "concluidos": 0}
    m = threading.Lock()

    def tarefa(primeiro, segundo, nome):
        primeiro.acquire()
        time.sleep(0.2)                       # garante a espera circular na 1ª tentativa
        if segundo.acquire(timeout=timeout):
            segundo.release()
            primeiro.release()
        else:                                 # timeout = suspeita de deadlock
            primeiro.release()                # quebra a espera circular
            with m:
                stats["detectados"] += 1
            time.sleep(random.uniform(0.01, 0.05))
            with A:                           # nova tentativa com ORDEM GLOBAL: A depois B
                with B:
                    pass
        with m:
            stats["concluidos"] += 1

    ths = [threading.Thread(target=tarefa, args=(A, B, "t1")),
           threading.Thread(target=tarefa, args=(B, A, "t2"))]
    t0 = time.perf_counter()
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    return {"deadlocks_detectados": stats["detectados"], "tarefas_concluidas": stats["concluidos"],
            "tempo_s": round(time.perf_counter() - t0, 3)}


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--saida", default="resultados/sincronizacao.csv")
    a = ap.parse_args()
    sys.setswitchinterval(1e-5)
    linhas = []

    def reg(demo, variante, rep, dados):
        linha = {"demo": demo, "variante": variante, "rep": rep,
                 "horario": time.strftime("%Y-%m-%dT%H:%M:%S"), **dados}
        linhas.append(linha)
        print(f"{demo:20s} {variante:22s} rep{rep}: " +
              ", ".join(f"{k}={v}" for k, v in dados.items()), flush=True)

    for rep in range(1, a.reps + 1):
        for v in ("sem_lock", "lock_global", "lock_curto"):
            reg("cache_compartilhado", v, rep, demo_cache(v))
        for seguro in (False, True):
            reg("log_concorrente", "com_mutex" if seguro else "sem_mutex", rep, demo_log(seguro))
        for usar in (False, True):
            reg("buffer_limitado", "com_mutex" if usar else "sem_mutex", rep, demo_buffer(usar))
        reg("buffer_limitado", "consumidor_bloqueado", rep, demo_consumidor_bloqueado())
        reg("deadlock", "real_sem_timeout", rep, demo_deadlock_real())
        reg("deadlock", "recuperavel_com_timeout", rep, demo_deadlock_recuperavel())

    saida = RAIZ / a.saida
    saida.parent.mkdir(parents=True, exist_ok=True)
    campos = []
    for l in linhas:
        for k in l:
            if k not in campos:
                campos.append(k)
    with open(saida, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    (saida.with_suffix(".json")).write_text(json.dumps(linhas, indent=2))
    print(f"\nResultados brutos: {saida}")


if __name__ == "__main__":
    main()
