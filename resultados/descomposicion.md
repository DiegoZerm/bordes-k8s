# Descomposición del tiempo

## 1. Costo fijo de arrancar pods (p = 1)

- Hueco entre el fin de una tarea y el inicio de la siguiente: mediana **4.0 s** (mín. 3, máx. 6; 135 huecos, resolución 1 s).
- Cómputo puro sumado de las 16 tareas: **65.9 s** en promedio.
- Tiempo de pared T(1): **134.1 s** en promedio.
- Es decir, **51 %** de T(1) no es procesar fotos: es crear el pod, arrancar Python, importar numpy y Pillow, listar la carpeta y escribir resultados.

## 2. Contención de CPU: ms promedio por foto

| p | ms por foto | respecto a p = 1 |
|---:|---:|---:|
| 1 | 8.91 | ×1.00 |
| 2 | 9.50 | ×1.07 |
| 4 | 11.02 | ×1.24 |
| 8 | 24.53 | ×2.75 |

La laptop tiene 4 núcleos físicos y 8 hilos, y además corre el control-plane de kind. Con p = 8 cada foto tarda más porque los pods se reparten núcleos con hyper-threading.

## 3. Desbalance I con cada criterio de reparto (simulado con los ms medidos)

| Reparto | I simulado |
|---|---:|
| block | 1.185 |
| cyclic | 1.119 |
| lpt por bytes (proyecto) | 1.065 |
| lpt por megapíxeles | 1.026 |
| lpt por ms reales (cota) | 1.000 |

Los ms por foto se toman de la corrida `b-block-p1-r1`; el I real de cada corrida también incluye ruido de la laptop.

## 4. Desbalance I medido: mediana de las 3 repeticiones

La mediana es menos sensible a un pico aislado de la laptop que el promedio de tabla.md.

| p | block | cyclic | lpt |
|---:|---:|---:|---:|
| 1 | 1.185 | 1.192 | 1.132 |
| 2 | 1.293 | 1.196 | 1.192 |
| 4 | 1.205 | 1.086 | 1.146 |
| 8 | 1.120 | 1.246 | 1.148 |
