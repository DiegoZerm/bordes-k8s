"""Análisis del barrido: speedup, eficiencia, fracción serial y desbalance.

Lee tiempos.csv (una fila por corrida) y produce en la carpeta de salida:
  tabla.csv / tabla.md   T(p), S(p), E(p), f e I promedio por estrategia y p
  speedup.png            S(p) y E(p) por estrategia, con la recta ideal
  desbalance.png         I promedio por estrategia y p

Con --detalle <carpeta de una corrida completa> (la que tiene resultados.csv)
agrega lo que piden las preguntas de análisis:
  costo_por_foto.png     ms contra bytes y contra megapíxeles
  detalle.md             correlaciones y qué índices tardaron más con cada estrategia

Fórmulas:
  S(p) = T(1) / T(p)        E(p) = S(p) / p
  f    = (1/S - 1/p) / (1 - 1/p)            (Amdahl despejada, p > 1)
  I    = max(t_i) / promedio(t_i)           (t_i = tiempo de cómputo de la tarea i)

Uso: python scripts/analyze.py [tiempos.csv] [carpeta_salida] [--detalle DIR --barrido DIR]
"""

import argparse
import csv
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORES = {"block": "#1f77b4", "cyclic": "#ff7f0e", "lpt": "#2ca02c"}
ORDEN = ["block", "cyclic", "lpt"]


def leer_tiempos(ruta: Path) -> dict[tuple[str, int], list[dict]]:
    grupos: dict[tuple[str, int], list[dict]] = defaultdict(list)
    with open(ruta, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            grupos[(fila["estrategia"], int(fila["p"]))].append(fila)
    return grupos


def tabla(grupos) -> list[dict]:
    estrategias = [e for e in ORDEN if any(k[0] == e for k in grupos)]
    filas = []
    for e in estrategias:
        ps = sorted(p for (ee, p) in grupos if ee == e)
        t1 = st.mean(float(r["T_s"]) for r in grupos[(e, 1)]) if (e, 1) in grupos else None
        for p in ps:
            ts = [float(r["T_s"]) for r in grupos[(e, p)]]
            T = st.mean(ts)
            S = t1 / T if t1 else None
            E = S / p if S else None
            f = (1 / S - 1 / p) / (1 - 1 / p) if S and p > 1 else None
            filas.append({
                "estrategia": e, "p": p, "n": len(ts),
                "T_s": round(T, 2), "T_desv_s": round(st.stdev(ts), 2) if len(ts) > 1 else 0.0,
                "S": round(S, 3) if S else "", "E": round(E, 3) if E else "",
                "f": round(f, 4) if f is not None else "",
                "I": round(st.mean(float(r["I"]) for r in grupos[(e, p)]), 3),
            })
    return filas


def escribir_tabla(filas, salida: Path) -> None:
    with open(salida / "tabla.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    lineas = ["| Estrategia | p | T(p) [s] | desv. [s] | S(p) | E(p) | f | I |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in filas:
        lineas.append(f"| {r['estrategia']} | {r['p']} | {r['T_s']:.2f} | {r['T_desv_s']:.2f} | "
                      f"{r['S'] or '—'} | {r['E'] or '—'} | {r['f'] if r['f'] != '' else '—'} | {r['I']} |")
    (salida / "tabla.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def graficas(filas, salida: Path, titulo: str) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    ps_todos = sorted({r["p"] for r in filas})
    a1.plot(ps_todos, ps_todos, "k--", lw=1, label="ideal S = p")
    for e in ORDEN:
        rs = [r for r in filas if r["estrategia"] == e]
        if not rs:
            continue
        a1.plot([r["p"] for r in rs], [r["S"] for r in rs], "o-", color=COLORES[e], label=e)
        a2.plot([r["p"] for r in rs], [r["E"] for r in rs], "o-", color=COLORES[e], label=e)
    a1.set(xlabel="p (pods simultáneos)", ylabel="Speedup S(p) [adimensional]",
           title="Speedup", xticks=ps_todos)
    a2.axhline(1, color="k", ls="--", lw=1)
    a2.set(xlabel="p (pods simultáneos)", ylabel="Eficiencia E(p) [adimensional]",
           title="Eficiencia", xticks=ps_todos, ylim=(0, 1.1))
    for a in (a1, a2):
        a.grid(alpha=0.3)
        a.legend()
    fig.suptitle(titulo)
    fig.tight_layout()
    fig.savefig(salida / "speedup.png", dpi=150)
    plt.close(fig)

    fig, a = plt.subplots(figsize=(6.5, 4))
    ancho = 0.25
    for k, e in enumerate(ORDEN):
        rs = [r for r in filas if r["estrategia"] == e]
        if rs:
            a.bar([ps_todos.index(r["p"]) + (k - 1) * ancho for r in rs], [r["I"] for r in rs],
                  ancho, color=COLORES[e], label=e)
    a.axhline(1, color="k", ls="--", lw=1)
    a.set(xticks=range(len(ps_todos)), xticklabels=ps_todos, xlabel="p (pods simultáneos)",
          ylabel="Desbalance I = max(t_i)/prom(t_i)", title="Desbalance de carga (16 tareas)")
    a.set_ylim(0.9, max(r["I"] for r in filas) * 1.08)
    a.legend()
    a.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(salida / "desbalance.png", dpi=150)
    plt.close(fig)


def pearson(x, y) -> float:
    mx, my = st.mean(x), st.mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = (sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)) ** 0.5
    return num / den


def detalle(dir_corrida: Path, dir_barrido: Path | None, salida: Path) -> None:
    with open(dir_corrida / "resultados.csv", newline="", encoding="utf-8") as f:
        ok = [r for r in csv.DictReader(f) if r["estado"] == "ok"]
    kb = [int(r["bytes"]) / 1024 for r in ok]
    mp = [float(r["megapixeles"]) for r in ok]
    ms = [float(r["ms"]) for r in ok]
    r_bytes, r_mp = pearson(kb, ms), pearson(mp, ms)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    a1.scatter(kb, ms, s=4, alpha=0.4)
    a1.set(xlabel="Tamaño del archivo [KiB]", ylabel="Tiempo de proceso [ms]",
           title=f"ms contra tamaño (r = {r_bytes:.3f})")
    a2.scatter(mp, ms, s=4, alpha=0.4, color="#2ca02c")
    a2.set(xlabel="Megapíxeles [MP]", title=f"ms contra megapíxeles (r = {r_mp:.3f})")
    for a in (a1, a2):
        a.grid(alpha=0.3)
    fig.suptitle(f"Costo por foto ({len(ok)} fotos, corrida {dir_corrida.name})")
    fig.tight_layout()
    fig.savefig(salida / "costo_por_foto.png", dpi=150)
    plt.close(fig)

    lineas = [f"# Detalle del análisis\n",
              f"Corrida de referencia para el costo por foto: `{dir_corrida.name}` "
              f"({len(ok)} fotos correctas).\n",
              f"- Correlación de Pearson ms–tamaño de archivo: **r = {r_bytes:.3f}**",
              f"- Correlación de Pearson ms–megapíxeles: **r = {r_mp:.3f}**",
              f"- ms por foto: mediana {st.median(ms):.2f}, mínimo {min(ms):.2f}, "
              f"máximo {max(ms):.2f}",
              f"- Megapíxeles: mediana {st.median(mp):.3f}, mínimo {min(mp):.3f}, "
              f"máximo {max(mp):.3f}\n"]

    # Por tarea: cuánto le tocó a cada índice con cada estrategia (p = 1, rep 1)
    por_foto = {r["archivo"]: r for r in ok}
    if dir_barrido is not None:
        for e in ORDEN:
            corridas = sorted(dir_barrido.glob(f"*-{e}-p1-r1.json"))
            if not corridas:
                continue
            s = json.loads(corridas[0].read_text(encoding="utf-8"))
            tareas = sorted(s["por_tarea"], key=lambda t: t["indice"])
            lineas.append(f"## {e} (corrida {corridas[0].stem}, I = {s['desbalance_I']})\n")
            lineas.append("| Índice | Fotos | MiB | MP totales | t_i [s] |")
            lineas.append("|---:|---:|---:|---:|---:|")
            parte_dir = dir_corrida.parent / corridas[0].stem
            mp_tarea = {}
            for t in tareas:
                csv_parte = parte_dir / f"part-{t['indice']:04d}.csv"
                if csv_parte.exists():
                    with open(csv_parte, newline="", encoding="utf-8") as f:
                        mp_tarea[t["indice"]] = sum(
                            float(r["megapixeles"]) for r in csv.DictReader(f) if r["estado"] == "ok")
            for t in tareas:
                lineas.append(f"| {t['indice']} | {t['fotos']} | {t['bytes'] / 2**20:.1f} | "
                              f"{mp_tarea.get(t['indice'], float('nan')):.1f} | {t['t_computo_s']:.2f} |")
            lento = max(tareas, key=lambda t: t["t_computo_s"])
            rapido = min(tareas, key=lambda t: t["t_computo_s"])
            lineas.append(f"\nMás lento: índice {lento['indice']} ({lento['t_computo_s']:.2f} s, "
                          f"{lento['fotos']} fotos). Más rápido: índice {rapido['indice']} "
                          f"({rapido['t_computo_s']:.2f} s, {rapido['fotos']} fotos).\n")
    del por_foto
    (salida / "detalle.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> None:
    raiz = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tiempos", type=Path, nargs="?", default=raiz / "resultados" / "tiempos.csv")
    ap.add_argument("salida", type=Path, nargs="?", default=raiz / "resultados")
    ap.add_argument("--detalle", type=Path, help="carpeta de una corrida con resultados.csv")
    ap.add_argument("--barrido", type=Path, help="carpeta con los summary.json del barrido")
    ap.add_argument("--titulo", default="Detección de bordes en kind (Oxford-IIIT Pet, 16 tareas)")
    a = ap.parse_args()

    a.salida.mkdir(parents=True, exist_ok=True)
    filas = tabla(leer_tiempos(a.tiempos))
    escribir_tabla(filas, a.salida)
    graficas(filas, a.salida, a.titulo)
    if a.detalle:
        detalle(a.detalle, a.barrido, a.salida)
    print((a.salida / "tabla.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
