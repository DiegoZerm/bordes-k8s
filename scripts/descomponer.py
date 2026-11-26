"""Descompone el tiempo del barrido para explicar la caída de eficiencia con datos.

Usa las salidas completas de cada corrida (datos/salida/<corrida>/) y escribe
resultados/descomposicion.md con:
  1. Costo fijo por pod: con p = 1 los pods van uno tras otro, así que el hueco
     entre el fin de una tarea y el inicio de la siguiente es arranque de pod.
  2. Contención de CPU: ms promedio por foto con cada p (la misma foto tarda
     más cuando hay más pods compitiendo por los núcleos de la laptop).
  3. Reparto alternativo: con los ms medidos de cada foto, qué desbalance I
     darían block, cyclic, LPT por bytes (el del proyecto) y LPT por megapíxeles.

Uso: python scripts/descomponer.py [datos/salida] [resultados]
"""

import csv
import heapq
import json
import statistics as st
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDAS = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "datos" / "salida"
DESTINO = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "resultados"
TAREAS = 16


def fecha(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")


def partes(corrida: Path) -> list[dict]:
    return sorted((json.loads(p.read_text()) for p in corrida.glob("part-*.json")),
                  key=lambda d: fecha(d["inicio"]))


def huecos_p1() -> tuple[list[float], list[float], list[float]]:
    huecos, computo, pared = [], [], []
    with open(RAIZ / "resultados" / "tiempos.csv", newline="") as f:
        tiempos = {r["corrida"]: float(r["T_s"]) for r in csv.DictReader(f)}
    for corrida in sorted(SALIDAS.glob("b-*-p1-r*")):
        ps = partes(corrida)
        for a, b in zip(ps, ps[1:]):
            huecos.append((fecha(b["inicio"]) - fecha(a["fin"])).total_seconds())
        computo.append(sum(p["t_computo_s"] for p in ps))
        pared.append(tiempos[corrida.name])
    return huecos, computo, pared


def ms_por_p() -> dict[int, float]:
    por_p: dict[int, list[float]] = {}
    for corrida in sorted(SALIDAS.glob("b-*-p*-r*")):
        p = int(corrida.name.split("-p")[1].split("-")[0])
        with open(corrida / "resultados.csv", newline="") as f:
            ms = [float(r["ms"]) for r in csv.DictReader(f) if r["estado"] == "ok"]
        por_p.setdefault(p, []).append(st.mean(ms))
    return {p: st.mean(v) for p, v in sorted(por_p.items())}


def lpt(pesos: list[float]) -> list[list[int]]:
    orden = sorted(range(len(pesos)), key=lambda i: -pesos[i])
    mont = [(0.0, t) for t in range(TAREAS)]
    asign: list[list[int]] = [[] for _ in range(TAREAS)]
    for i in orden:
        carga, t = heapq.heappop(mont)
        asign[t].append(i)
        heapq.heappush(mont, (carga + pesos[i], t))
    return asign


def desbalance(asign, ms) -> float:
    cargas = [sum(ms[i] for i in a) for a in asign]
    return max(cargas) / st.mean(cargas)


def repartos() -> dict[str, float]:
    with open(SALIDAS / "b-block-p1-r1" / "resultados.csv", newline="") as f:
        filas = sorted((r for r in csv.DictReader(f) if r["estado"] == "ok"),
                       key=lambda r: r["archivo"])
    ms = [float(r["ms"]) for r in filas]
    bytes_ = [float(r["bytes"]) for r in filas]
    mp = [float(r["megapixeles"]) for r in filas]
    n = len(filas)
    base, extra = divmod(n, TAREAS)
    block, i = [], 0
    for t in range(TAREAS):
        k = base + (1 if t < extra else 0)
        block.append(list(range(i, i + k)))
        i += k
    return {
        "block": desbalance(block, ms),
        "cyclic": desbalance([list(range(t, n, TAREAS)) for t in range(TAREAS)], ms),
        "lpt por bytes (proyecto)": desbalance(lpt(bytes_), ms),
        "lpt por megapíxeles": desbalance(lpt(mp), ms),
        "lpt por ms reales (cota)": desbalance(lpt(ms), ms),
    }


def main() -> None:
    huecos, computo, pared = huecos_p1()
    ms = ms_por_p()
    rep = repartos()
    arranque = st.median(huecos)
    l = ["# Descomposición del tiempo\n",
         "## 1. Costo fijo de arrancar pods (p = 1)\n",
         f"- Hueco entre el fin de una tarea y el inicio de la siguiente: mediana **{arranque:.1f} s** "
         f"(mín. {min(huecos):.0f}, máx. {max(huecos):.0f}; {len(huecos)} huecos, resolución 1 s).",
         f"- Cómputo puro sumado de las 16 tareas: **{st.mean(computo):.1f} s** en promedio.",
         f"- Tiempo de pared T(1): **{st.mean(pared):.1f} s** en promedio.",
         f"- Es decir, **{100 * (1 - st.mean(computo) / st.mean(pared)):.0f} %** de T(1) no es "
         "procesar fotos: es crear el pod, arrancar Python, importar numpy y Pillow, listar la "
         "carpeta y escribir resultados.\n",
         "## 2. Contención de CPU: ms promedio por foto\n",
         "| p | ms por foto | respecto a p = 1 |", "|---:|---:|---:|"]
    for p, v in ms.items():
        l.append(f"| {p} | {v:.2f} | ×{v / ms[1]:.2f} |")
    l += ["", "La laptop tiene 4 núcleos físicos y 8 hilos, y además corre el control-plane de kind. "
          "Con p = 8 cada foto tarda más porque los pods se reparten núcleos con hyper-threading.\n",
          "## 3. Desbalance I con cada criterio de reparto (simulado con los ms medidos)\n",
          "| Reparto | I simulado |", "|---|---:|"]
    for k, v in rep.items():
        l.append(f"| {k} | {v:.3f} |")
    l += ["", "Los ms por foto se toman de la corrida `b-block-p1-r1`; el I real de cada corrida "
          "también incluye ruido de la laptop.\n",
          "## 4. Desbalance I medido: mediana de las 3 repeticiones\n",
          "La mediana es menos sensible a un pico aislado de la laptop que el promedio de tabla.md.\n",
          "| p | block | cyclic | lpt |", "|---:|---:|---:|---:|"]
    with open(RAIZ / "resultados" / "tiempos.csv", newline="") as f:
        medidos: dict[tuple[str, int], list[float]] = {}
        for r in csv.DictReader(f):
            medidos.setdefault((r["estrategia"], int(r["p"])), []).append(float(r["I"]))
    for p in sorted({k[1] for k in medidos}):
        l.append(f"| {p} | " + " | ".join(f"{st.median(medidos[(e, p)]):.3f}"
                                         for e in ("block", "cyclic", "lpt")) + " |")
    (DESTINO / "descomposicion.md").write_text("\n".join(l) + "\n")
    print("\n".join(l))


if __name__ == "__main__":
    main()
