"""Worker del Job indexado: procesa la parte del lote que le toca a su índice.

Cada pod lista las fotos en el mismo orden, decide cuáles le tocan según su
índice (JOB_COMPLETION_INDEX) y la estrategia de reparto, y aplica el pipeline
escala de grises -> desenfoque gaussiano -> Sobel -> umbral.

Escribe en la carpeta de salida:
  part-XXXX.csv   una fila por foto (tamaño, megapíxeles, ms, proporción de bordes)
  part-XXXX.json  resumen de la tarea (tiempo de cómputo, nodo, fotos, errores)
  bordes/         las imágenes de bordes, solo si GUARDAR_BORDES=1

Variables de entorno (todas con valor por defecto para probar en local):
  JOB_COMPLETION_INDEX  índice de la tarea (lo pone Kubernetes)
  TAREAS                total de tareas (completions)
  ESTRATEGIA            block | cyclic | lpt
  ENTRADA               carpeta con las fotos
  SALIDA                carpeta donde se escriben las partes
  LIMITE                cuántas fotos usar (0 = todas)
  GUARDAR_BORDES        1 para guardar los PNG de bordes
  FALLAR_INDICE         índice que falla a propósito en su primer intento (-1 = ninguno)
  NODE_NAME, POD_NAME   los pone Kubernetes con la Downward API
"""

import csv
import heapq
import json
import os
import socket
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

EXTENSIONES = {".jpg", ".jpeg", ".png"}
UMBRAL = 100.0  # magnitud de Sobel (0 a ~1440) a partir de la cual un píxel es borde
RADIO_GAUSS = 1.4


# ---------------------------------------------------------------------------
# Reparto
# ---------------------------------------------------------------------------
def listar_fotos(entrada: Path, limite: int) -> list[tuple[str, int]]:
    """Lista (nombre, bytes) en orden alfabético: todos los pods ven lo mismo."""
    fotos = sorted(
        p for p in entrada.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES
    )
    if limite > 0:
        fotos = fotos[:limite]
    return [(p.name, p.stat().st_size) for p in fotos]


def repartir(fotos: list[tuple[str, int]], tareas: int, estrategia: str) -> list[list[int]]:
    """Devuelve, para cada tarea, los índices de las fotos que le tocan."""
    n = len(fotos)
    asignacion: list[list[int]] = [[] for _ in range(tareas)]
    if estrategia == "block":
        # Bloques contiguos de la lista ordenada; los primeros n % tareas llevan una extra
        base, extra = divmod(n, tareas)
        inicio = 0
        for t in range(tareas):
            fin = inicio + base + (1 if t < extra else 0)
            asignacion[t] = list(range(inicio, fin))
            inicio = fin
    elif estrategia == "cyclic":
        # Foto i a la tarea i mod tareas
        for i in range(n):
            asignacion[i % tareas].append(i)
    elif estrategia == "lpt":
        # Longest Processing Time: de mayor a menor tamaño de archivo,
        # cada foto a la tarea con menos bytes acumulados (empate: menor índice)
        orden = sorted(range(n), key=lambda i: (-fotos[i][1], fotos[i][0]))
        monticulo = [(0, t) for t in range(tareas)]
        for i in orden:
            carga, t = heapq.heappop(monticulo)
            asignacion[t].append(i)
            heapq.heappush(monticulo, (carga + fotos[i][1], t))
    else:
        raise ValueError(f"Estrategia desconocida: {estrategia}")
    return asignacion


# ---------------------------------------------------------------------------
# Pipeline de bordes
# ---------------------------------------------------------------------------
def sobel(gris: np.ndarray) -> np.ndarray:
    """Magnitud del gradiente de Sobel con slicing de numpy (sin bordes de 1 px)."""
    g = gris.astype(np.float32)
    gx = (
        (g[:-2, 2:] + 2 * g[1:-1, 2:] + g[2:, 2:])
        - (g[:-2, :-2] + 2 * g[1:-1, :-2] + g[2:, :-2])
    )
    gy = (
        (g[2:, :-2] + 2 * g[2:, 1:-1] + g[2:, 2:])
        - (g[:-2, :-2] + 2 * g[:-2, 1:-1] + g[:-2, 2:])
    )
    return np.hypot(gx, gy)


def detectar_bordes(ruta: Path) -> tuple[np.ndarray, int, int]:
    with Image.open(ruta) as img:
        ancho, alto = img.size
        gris = img.convert("L")  # escala de grises (también resuelve CMYK, paleta, RGBA)
    suave = gris.filter(ImageFilter.GaussianBlur(RADIO_GAUSS))
    magnitud = sobel(np.asarray(suave))
    return magnitud > UMBRAL, ancho, alto


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def entero(nombre: str, defecto: int) -> int:
    return int(os.environ.get(nombre, defecto))


def main() -> int:
    indice = entero("JOB_COMPLETION_INDEX", 0)
    tareas = entero("TAREAS", 16)
    estrategia = os.environ.get("ESTRATEGIA", "block")
    entrada = Path(os.environ.get("ENTRADA", "/data/entrada/images"))
    salida = Path(os.environ.get("SALIDA", "/data/salida/local"))
    limite = entero("LIMITE", 0)
    guardar = os.environ.get("GUARDAR_BORDES", "0") == "1"
    fallar = entero("FALLAR_INDICE", -1)
    nodo = os.environ.get("NODE_NAME", socket.gethostname())
    pod = os.environ.get("POD_NAME", socket.gethostname())

    salida.mkdir(parents=True, exist_ok=True)

    # Prueba de tolerancia a fallos: el índice elegido sale con código 1 la
    # primera vez. La marca queda en el volumen compartido, así que el
    # reintento (otro pod, quizá en otro nodo) ya no falla.
    if indice == fallar:
        marca = salida / f"fallo-{indice:04d}.marca"
        if not marca.exists():
            marca.write_text(f"falló a propósito en {pod} ({nodo})\n")
            print(f"[{indice}] Fallo provocado en el primer intento", flush=True)
            return 1
        print(f"[{indice}] Reintento después del fallo provocado", flush=True)

    t0_total = time.perf_counter()
    inicio_iso = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    fotos = listar_fotos(entrada, limite)
    mias = repartir(fotos, tareas, estrategia)[indice]
    if guardar:
        (salida / "bordes").mkdir(exist_ok=True)

    filas = []
    errores = 0
    t_computo = 0.0
    for i in mias:
        nombre, tam = fotos[i]
        t0 = time.perf_counter()
        try:
            bordes, ancho, alto = detectar_bordes(entrada / nombre)
            ms = (time.perf_counter() - t0) * 1000
            proporcion = float(bordes.mean())
            if guardar:
                Image.fromarray((bordes * 255).astype(np.uint8)).save(
                    salida / "bordes" / (Path(nombre).stem + ".png")
                )
            filas.append([nombre, tam, ancho, alto, round(ancho * alto / 1e6, 4),
                          round(ms, 3), round(proporcion, 5), indice, nodo, "ok"])
        except Exception as e:  # una foto dañada no detiene al pod
            ms = (time.perf_counter() - t0) * 1000
            errores += 1
            print(f"[{indice}] Error en {nombre}: {e}", file=sys.stderr, flush=True)
            filas.append([nombre, tam, "", "", "", round(ms, 3), "", indice, nodo,
                          f"error: {type(e).__name__}"])
        t_computo += ms / 1000

    base = salida / f"part-{indice:04d}"
    with open(f"{base}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["archivo", "bytes", "ancho", "alto", "megapixeles", "ms",
                    "proporcion_bordes", "indice", "nodo", "estado"])
        w.writerows(filas)

    resumen = {
        "indice": indice,
        "tareas": tareas,
        "estrategia": estrategia,
        "nodo": nodo,
        "pod": pod,
        "fotos": len(mias),
        "bytes": sum(fotos[i][1] for i in mias),
        "errores": errores,
        "t_computo_s": round(t_computo, 4),
        "t_total_s": round(time.perf_counter() - t0_total, 4),
        "inicio": inicio_iso,
        "fin": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    Path(f"{base}.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False))
    print(f"[{indice}] {len(mias)} fotos en {t_computo:.2f} s en {nodo} "
          f"({errores} errores)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
