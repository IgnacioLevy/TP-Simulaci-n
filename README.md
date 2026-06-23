# Simulador "Palacio Ferreyra" — TP5 Simulación 2026

Simulación por eventos discretos de una muestra de arte, con stand de
cerveza modelado mediante una ecuación diferencial resuelta por
Runge-Kutta de 4to orden.

## Cómo correrlo

1. Necesitás Python 3.10+ con **Tkinter** (viene incluido en la
   instalación estándar de Python en Windows; en Linux instalalo con
   `sudo apt install python3-tk` si te falta).
2. Instalá las dependencias:
   ```
   pip install -r requirements.txt
   ```
3. Ejecutá:
   ```
   python main.py
   ```

## Estructura

```
palacio_ferreyra/
├── main.py                 # Punto de entrada
├── requirements.txt
├── core/
│   ├── motor_eventos.py    # Simulador: lógica de eventos discretos
│   ├── visitante.py        # Modelo del visitante (estado, RNDs, tiempos)
│   └── runge_kutta.py      # Integración numérica de la degustación
└── ui/
    └── interfaz.py         # Interfaz gráfica (Tkinter + matplotlib)
```

## Qué resolvimos de la consigna

- **Tope de iteraciones / tiempo X**: el motor corta a las 100.000
  iteraciones o al llegar a las 22 hs (lo que pase primero). Configurable
  desde la pestaña *Parámetros*.
- **Mostrar i iteraciones desde j**: campos `j` e `i` en la pestaña
  *Parámetros*; el motor solo guarda esas filas (más la fila final del
  día, sin objetos temporales).
- **Última fila sin objetos temporales**: al llegar a `Fin_Jornada` se
  guarda una fila con `Visitantes_Activos_Detalle` vacío.
- **Todos los parámetros modificables**: medias/desvíos de las 3
  puertas, rango de la cerveza, % folletos, % fotografía, % degustación,
  cantidad de días, j, i y tope de iteraciones — todos editables en la UI.
- **Vector de estado con detalle por visitante**: cada fila trae un campo
  `Visitantes_Activos_Detalle` con el snapshot completo de cada visitante
  presente en el sistema en ese instante (edad, sala, estado, números
  aleatorios usados). Se ve seleccionando una fila en la pestaña
  
  *Vector de Estado*.
- **Números aleatorios mostrados**: cada `Visitante` guarda el rnd usado
  para su edad, decisión de folletos, ventanilla, tiempo de folletos,
  tiempo de sala, decisión de fotografía/cerveza y tiempo de cerveza.
- **Tablas de Runge-Kutta**: se listan por visitante en la pestaña
  *Runge-Kutta*, con cada paso `t`, `C(t)`, `dC/dt`.
- **Métricas obligatorias**: tiempo promedio en cola de informes y
  tiempo promedio de permanencia en la exposición.
- **Cada 15 minutos**: cantidad de personas en Pintura y Fotografía,
  visible en tabla + gráfico en la pestaña *Salas / 15 min*.
- **5 métricas extra** :
  1. Total de visitantes que pidieron folletos.
  2. Total de cervezas servidas.
  3. Edad promedio de quienes degustaron.
  4. Total de visitantes que entraron a Fotografía.
  5. Personas que abandonaron tras Pintura (no fueron a Fotografía).
 
- **Simular varios días**: parámetro "Días a simular"; al llegar a las
  22 hs se reinicia el día (colas y salas vacías) pero las métricas se
  acumulan en todo el período simulado.

## Notas / posibles mejoras futuras

- Las probabilidades de elegir ventanilla 1 vs 2 quedaron fijas en 50/50
  porque el enunciado no las menciona como parámetro variable.
- Si un visitante queda "a mitad de recorrido" justo cuando cierra el
  palacio (22 hs), no se cuenta su tiempo de permanencia porque no llegó
  a completar el circuito ese día.
