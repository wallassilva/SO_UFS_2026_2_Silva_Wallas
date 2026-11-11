#!/usr/bin/env python3
"""Consolida os JSON brutos: consolidado.csv, resumo.csv e grafico_c1_c2.png"""
import csv, json, statistics as st, sys
from pathlib import Path

D = Path(sys.argv[1] if len(sys.argv) > 1 else "resultados/bruto")
CAMPOS = ["arquivo", "cond", "rep", "rc", "wall_host_s", "valido", "status", "correto", "n_feito",
          "wall_s", "cpu_proc_s", "trab_por_s", "cpu_max", "memory_max", "memory_swap_max", "pids_max",
          "usage_usec", "nr_periods", "nr_throttled", "throttled_usec",
          "memory_current", "memory_peak", "rss_pico_kib", "motivo"]

linhas = []
with open(D / "status_execucoes.csv", newline="") as f:
    for s in csv.DictReader(f):
        l = {"arquivo": s["arquivo"], "cond": s["cond"], "rep": s["rep"], "rc": s["rc"],
             "wall_host_s": s["wall_host_s"], "valido": False, "motivo": ""}
        try:
            r = json.loads((D / s["arquivo"]).read_text().strip().splitlines()[-1])
            d = r.pop("cpu_stat_delta", {})
            l.update({k: r.get(k) for k in CAMPOS if k in r})
            l.update({k: d.get(k) for k in ("usage_usec", "nr_periods", "nr_throttled", "throttled_usec")})
            l["valido"] = bool(r.get("correto")) and s["rc"] == "0"
            if not l["valido"]:
                l["motivo"] = f"status={r.get('status')} correto={r.get('correto')} rc={s['rc']}"
        except Exception as e:
            l["motivo"] = f"sem JSON valido ({type(e).__name__}); ver .err"
        linhas.append(l)

with open(D / "consolidado.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
    w.writeheader(); w.writerows(linhas)

def num(l, k):
    try: return float(l[k])
    except (TypeError, ValueError, KeyError): return None

resumo = []
for c in sorted({l["cond"] for l in linhas}):
    v = [l for l in linhas if l["cond"] == c and l["valido"]]
    t = [num(l, "trab_por_s") for l in v]
    w = [num(l, "wall_s") for l in v]
    th = [num(l, "nr_throttled") for l in v if num(l, "nr_throttled") is not None]
    tu = [num(l, "throttled_usec") for l in v if num(l, "throttled_usec") is not None]
    if not t:
        continue
    resumo.append({
        "cond": c, "n_validas": len(v),
        "mediana_trab_por_s": round(st.median(t), 1), "min_trab_por_s": min(t), "max_trab_por_s": max(t),
        "cv_pct": round(100 * st.stdev(t) / st.mean(t), 2) if len(t) > 1 else "",
        "mediana_wall_s": round(st.median(w), 3),
        "mediana_nr_throttled": st.median(th) if th else "", "mediana_throttled_usec": st.median(tu) if tu else "",
    })
with open(D / "resumo.csv", "w", newline="") as f:
    if resumo:
        w = csv.DictWriter(f, fieldnames=list(resumo[0])); w.writeheader(); w.writerows(resumo)

print(f"{len(linhas)} tentativas, {sum(l['valido'] for l in linhas)} validas")
for r in resumo: print(r)
for l in linhas:
    if not l["valido"]: print("INVALIDA:", l["arquivo"], l["motivo"])
if len(resumo) == 2:
    a, b = resumo
    print(f"razao mediana trab/s {b['cond']}/{a['cond']} = {b['mediana_trab_por_s'] / a['mediana_trab_por_s']:.2f}")

try:
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit("matplotlib ausente: sudo dnf install python3-matplotlib (CSV ja foi gerado)")
conds = [r["cond"] for r in resumo]
fig, ax = plt.subplots(1, 2, figsize=(10, 4))
for a, campo, rot in ((ax[0], "wall_s", "Tempo de parede (s)"), (ax[1], "trab_por_s", "Trabalho concluído (iterações/s)")):
    for i, c in enumerate(conds):
        ys = [num(l, campo) for l in linhas if l["cond"] == c and l["valido"]]
        a.bar(i, st.median(ys), alpha=0.35, label="mediana" if i == 0 else None)
        a.scatter([i] * len(ys), ys, color="k", zorder=3, label="repetições" if i == 0 else None)
    a.set_xticks(range(len(conds)))
    a.set_xticklabels([f"{c}\n(n={r['n_validas']})" for c, r in zip(conds, resumo)])
    a.set_ylabel(rot); a.legend()
fig.suptitle("C1 (0,5 CPU) vs C2 (1,0 CPU): trabalho fixo, 3 repetições por condição")
fig.tight_layout(); fig.savefig(D / "grafico_c1_c2.png", dpi=150)
print("grafico:", D / "grafico_c1_c2.png")
