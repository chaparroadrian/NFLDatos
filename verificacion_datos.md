# Verificación de los datos y oportunidades de análisis

## Alcance

Este documento verifica la lectura descrita en `diagnostico_inicial.md`, profundiza en las relaciones entre tablas y traduce los hallazgos a preguntas útiles para un entrenador de NFL. También compara esas preguntas con aplicaciones públicas existentes.

Los archivos originales de `data/` se trataron como solo lectura. Los 122 CSV de tracking se procesaron uno a la vez para no mantener los 8.3 millones de renglones en memoria. No se entrenó un modelo ni se hicieron visualizaciones.

## 1. Código utilizado

Los bloques siguientes consolidan el código ejecutado durante la revisión. Se ejecutaron con el Python del proyecto:

```bash
.venv/bin/python <script.py>
```

### 1.1 Lectura, esquema, faltantes, duplicados y llaves

```python
from pathlib import Path
from collections import Counter
import pandas as pd

ROOT = Path("data/nfl-big-data-bowl-regional-event-data-main/data")

games = pd.read_csv(ROOT / "games.csv")
plays = pd.read_csv(ROOT / "plays.csv")
players = pd.read_csv(ROOT / "players.csv")
pff = pd.read_csv(ROOT / "pffScoutingData.csv")
tracking_files = sorted((ROOT / "tracking").glob("tracking_*.csv"))

for name, df in {
    "games": games,
    "plays": plays,
    "players": players,
    "pffScoutingData": pff,
}.items():
    resumen = pd.DataFrame({
        "dtype": df.dtypes.astype(str),
        "faltantes": df.isna().sum(),
        "porcentaje_faltante": (100 * df.isna().mean()).round(1),
        "valores_unicos": df.nunique(dropna=True),
    })
    print(name, df.shape, "duplicados completos:", df.duplicated().sum())
    print(resumen)

print("gameId duplicado:", games.duplicated("gameId").sum())
print("jugada duplicada:", plays.duplicated(["gameId", "playId"]).sum())
print("nflId duplicado:", players.duplicated("nflId").sum())
print(
    "jugador-jugada PFF duplicado:",
    pff.duplicated(["gameId", "playId", "nflId"]).sum(),
)

play_keys = pd.MultiIndex.from_frame(plays[["gameId", "playId"]])
pff_play_keys = pd.MultiIndex.from_frame(
    pff[["gameId", "playId"]].drop_duplicates()
)
print("jugadas sin PFF:", (~play_keys.isin(pff_play_keys)).sum())
print("PFF fuera de plays:", (~pff_play_keys.isin(play_keys)).sum())
print("nflId PFF fuera de players:", (~pff.nflId.isin(players.nflId)).sum())

# Fechas contra el formato documentado.
birth_parsed = pd.to_datetime(players.birthDate, format="%Y-%m-%d", errors="coerce")
bad_birth_format = players.birthDate.notna() & birth_parsed.isna()
print(players.loc[bad_birth_format, "birthDate"].value_counts())
```

### 1.2 Estructura de roles PFF y relaciones con el resultado

```python
import numpy as np

roles = pff.pivot_table(
    index=["gameId", "playId"],
    columns="pff_role",
    values="nflId",
    aggfunc="count",
    fill_value=0,
)
roles["ofensiva"] = roles[["Pass", "Pass Block", "Pass Route"]].sum(axis=1)
roles["defensiva"] = roles[["Coverage", "Pass Rush"]].sum(axis=1)

print(roles.describe())
print("ofensivas distintas de 11:", (roles.ofensiva != 11).sum())
print("defensivas distintas de 11:", (roles.defensiva != 11).sum())
print("rushers por jugada:", roles["Pass Rush"].value_counts().sort_index())
print("bloqueadores por jugada:", roles["Pass Block"].value_counts().sort_index())

# Una etiqueta binaria a nivel jugada. Es una síntesis descriptiva, no una
# definición universal de presión.
pressure = pff.groupby(["gameId", "playId"]).agg(
    hit=("pff_hit", "max"),
    hurry=("pff_hurry", "max"),
    sack=("pff_sack", "max"),
    beaten=("pff_beatenByDefender", "max"),
    hit_allowed=("pff_hitAllowed", "max"),
    hurry_allowed=("pff_hurryAllowed", "max"),
    sack_allowed=("pff_sackAllowed", "max"),
).fillna(0)
pressure["evento_defensivo"] = pressure[["hit", "hurry", "sack"]].max(axis=1)
pressure["cargo_ofensivo"] = pressure[
    ["hit_allowed", "hurry_allowed", "sack_allowed"]
].max(axis=1)

analysis = (
    plays
    .merge(roles[["Pass Rush", "Pass Block"]], on=["gameId", "playId"])
    .merge(pressure, on=["gameId", "playId"])
)
analysis["complete"] = analysis.passResult.eq("C")

print(analysis.groupby("evento_defensivo").agg(
    jugadas=("playId", "size"),
    completos=("complete", "mean"),
    yardas=("playResult", "mean"),
    sacks_resultado=("passResult", lambda s: s.eq("S").mean()),
    intercepciones=("passResult", lambda s: s.eq("IN").mean()),
))

print(analysis.groupby("Pass Rush").agg(
    jugadas=("playId", "size"),
    evento_defensivo=("evento_defensivo", "mean"),
    sack=("sack", "mean"),
    completos=("complete", "mean"),
    yardas=("playResult", "mean"),
))

print(analysis.groupby("pff_passCoverageType").agg(
    jugadas=("playId", "size"),
    evento_defensivo=("evento_defensivo", "mean"),
    sack=("sack", "mean"),
    completos=("complete", "mean"),
    yardas=("playResult", "mean"),
))

print(analysis.groupby("pff_playAction").agg(
    jugadas=("playId", "size"),
    evento_defensivo=("evento_defensivo", "mean"),
    sack=("sack", "mean"),
    completos=("complete", "mean"),
    yardas=("playResult", "mean"),
    rushers=("Pass Rush", "mean"),
    defensores_en_caja=("defendersInBox", "mean"),
))
```

### 1.3 Validación de personal ofensivo y defensivo

```python
import re

# personnelO enumera jugadores de habilidad y, en paquetes inusuales, también
# QB/OL. Por eso se revisan las cadenas, no se presupone que siempre sumen 5.
def offensive_count(value):
    if pd.isna(value):
        return np.nan
    return sum(map(int, re.findall(r"(\d+)\s+(?:QB|OL|RB|TE|WR)", value)))

def defensive_count(value):
    if pd.isna(value):
        return np.nan
    return sum(map(int, re.findall(r"(\d+)\s+(?:DL|LB|DB)", value)))

print(plays.personnelO.map(offensive_count).value_counts(dropna=False))
print(plays.personnelD.map(defensive_count).value_counts(dropna=False))
print(pd.crosstab(plays.pff_passCoverage, plays.pff_passCoverageType))
```

### 1.4 Tracking: procesamiento por archivo, eventos y extremos

```python
from collections import Counter

tracking_play_keys = set()
tracking_ids = set()
missing = Counter()
rows = 0
duplicate_tracking_keys = 0
extremes = Counter()
team_mismatches = 0
summaries = []

play_teams = plays[[
    "gameId", "playId", "possessionTeam", "defensiveTeam",
    "absoluteYardlineNumber", "passResult",
]]

for path in tracking_files:
    df = pd.read_csv(path)
    rows += len(df)
    missing.update(df.isna().sum().to_dict())
    duplicate_tracking_keys += df.duplicated(
        ["gameId", "playId", "nflId", "frameId"]
    ).sum()

    tracking_play_keys.update(
        map(tuple, df[["gameId", "playId"]].drop_duplicates().to_numpy())
    )
    tracking_ids.update(df.nflId.dropna().astype(int))

    merged = df.merge(
        play_teams[["gameId", "playId", "possessionTeam", "defensiveTeam"]],
        on=["gameId", "playId"],
    )
    valid_team = (
        merged.team.eq("football")
        | merged.team.eq(merged.possessionTeam)
        | merged.team.eq(merged.defensiveTeam)
    )
    team_mismatches += (~valid_team).sum()

    extremes["player_x_out"] += (
        df.team.ne("football") & ~df.x.between(0, 120)
    ).sum()
    extremes["ball_x_out"] += (
        df.team.eq("football") & ~df.x.between(0, 120)
    ).sum()
    extremes["player_y_out"] += (
        df.team.ne("football") & ~df.y.between(0, 53.3)
    ).sum()
    extremes["ball_y_out"] += (
        df.team.eq("football") & ~df.y.between(0, 53.3)
    ).sum()
    extremes["player_speed_gt_15"] += (
        df.team.ne("football") & df.s.gt(15)
    ).sum()
    extremes["ball_speed_gt_15"] += (
        df.team.eq("football") & df.s.gt(15)
    ).sum()
    extremes["player_accel_gt_15"] += (
        df.team.ne("football") & df.a.gt(15)
    ).sum()
    extremes["ball_accel_gt_15"] += (
        df.team.eq("football") & df.a.gt(15)
    ).sum()

    # Una fila por cuadro: la del balón. Se prioriza la etiqueta manual y se
    # usa la etiqueta auto solo si la manual no existe.
    ball = df[df.team.eq("football")]
    for (game_id, play_id), play_ball in ball.groupby(["gameId", "playId"]):
        def event_frame(primary, fallback):
            values = play_ball.loc[play_ball.event.eq(primary), "frameId"]
            if values.empty:
                values = play_ball.loc[play_ball.event.eq(fallback), "frameId"]
            return values.iloc[0] if len(values) else np.nan

        snap = event_frame("ball_snap", "autoevent_ballsnap")
        throw = event_frame("pass_forward", "autoevent_passforward")
        snap_row = play_ball[play_ball.frameId.eq(snap)]
        summaries.append({
            "gameId": game_id,
            "playId": play_id,
            "frames": len(play_ball),
            "snap": snap,
            "throw": throw,
            "ball_x_snap": snap_row.x.iloc[0] if len(snap_row) else np.nan,
            "min_ball_rows_per_frame": play_ball.groupby("frameId").size().min(),
            "max_ball_rows_per_frame": play_ball.groupby("frameId").size().max(),
        })

tracking_summary = pd.DataFrame(summaries).merge(
    play_teams, on=["gameId", "playId"]
)
tracking_summary["time_to_throw"] = (
    tracking_summary.throw - tracking_summary.snap
) / 10
tracking_summary["los_difference"] = (
    tracking_summary.ball_x_snap - tracking_summary.absoluteYardlineNumber
).abs()

print("renglones:", rows)
print("duplicados de llave:", duplicate_tracking_keys)
print("equipos inconsistentes:", team_mismatches)
print("extremos:", extremes)
print("snap disponible:", tracking_summary.snap.notna().sum())
print("pase disponible:", tracking_summary.throw.notna().sum())
print(tracking_summary.time_to_throw.describe())
print(tracking_summary.los_difference.describe())
```

**Corrección metodológica importante:** la primera exploración combinó `ball_snap` y `autoevent_ballsnap` y tomó el primer evento cronológico. Eso puede elegir el evento automático antes del snap manual y produjo un máximo aparente de 19.2 segundos. Al priorizar `ball_snap` y usar `autoevent_ballsnap` solo como respaldo, el máximo observado baja a 9.8 segundos. Esta segunda forma es la usada en las conclusiones de este documento.

## 2. Resultados observados

### 2.1 La lectura y las llaves son correctas

- `games`: 122 × 7.
- `plays`: 8,557 × 32.
- `players`: 1,679 × 7.
- `pffScoutingData`: 188,254 × 15.
- Tracking: 8,314,178 × 16, repartido en 122 archivos con el mismo esquema.
- No hay duplicados en las llaves declaradas.
- Las 8,557 jugadas aparecen en plays, PFF y tracking.
- Los 1,679 jugadores aparecen en players, PFF y tracking.
- Todos los equipos de tracking son el balón o uno de los dos equipos de la jugada. Hubo 0 inconsistencias en 8.3 millones de renglones.
- Cada jugada tiene 22 jugadores en PFF: 11 roles ofensivos y 11 defensivos. Esa relación se cumple en las 8,557 jugadas.
- Cada cuadro tiene exactamente una fila del balón.

Esto permite unir con seguridad en dos niveles:

```text
partido:         gameId
jugada:          gameId + playId
jugador-jugada:  gameId + playId + nflId
cuadro:          gameId + playId + nflId + frameId
```

Para el balón, `nflId` es nulo; por eso `team == "football"` es el identificador práctico.

### 2.2 La tabla PFF describe la estructura completa de cada jugada

Promedios por jugada:

| Rol | Jugadores promedio | Mínimo | Máximo |
|---|---:|---:|---:|
| Pass | 1.00 | 1 | 1 |
| Pass Block | 5.38 | 5 | 9 |
| Pass Route | 4.62 | 1 | 5 |
| Pass Rush | 4.25 | 0 | 8 |
| Coverage | 6.75 | 3 | 11 |

Las identidades se cumplen exactamente:

```text
Pass + Pass Block + Pass Route = 11
Pass Rush + Coverage = 11
```

Distribución de pass rushers:

| Rushers | Jugadas |
|---:|---:|
| 0–2 | 19 |
| 3 | 420 |
| 4 | 6,011 |
| 5 | 1,689 |
| 6 | 348 |
| 7 | 69 |
| 8 | 1 |

La defensa mandó cuatro rushers en 70.2% de las jugadas. Cinco o más aparecen en 24.6%. Los extremos de 0–2 y 8 tienen muy pocas observaciones y no permiten conclusiones estables.

### 2.3 Indicadores PFF: los nulos dependen del rol

- `pff_hit`, `pff_hurry` y `pff_sack` solo tienen datos para `Coverage` y `Pass Rush`.
- Los indicadores de responsabilidad ofensiva solo tienen datos para `Pass Block` y una parte de `Pass Route`.
- `pff_blockType` aparece en 45,874 renglones `Pass Block` y 2,030 `Pass Route`. Estos últimos representan chips o ayuda antes de salir a ruta, no un error de clasificación.
- `pff_nflIdBlockedPlayer` nunca es igual al propio `nflId`, lo cual es coherente con que apunte a un oponente.

Al resumir por jugada:

| Indicador | Proporción de jugadas |
|---|---:|
| Algún hit, hurry o sack defensivo | 37.6% |
| Algún hit | 9.3% |
| Algún hurry | 27.2% |
| Algún sack PFF | 6.3% |
| Algún bloqueador vencido | 19.8% |
| Algún cargo ofensivo por hit/hurry/sack | 29.0% |

Estos indicadores no son intercambiables. Las marcas defensivas y los cargos ofensivos coinciden en 2,483 jugadas, pero hay 733 con cargo ofensivo y sin marca defensiva equivalente. No debe asumirse que son dos copias del mismo concepto. Hace falta estudiar las reglas de anotación de PFF o revisar video para explicar esa diferencia.

### 2.4 Asociaciones descriptivas, no efectos causales

Se definió `evento_defensivo = 1` si al menos un jugador tuvo `pff_hit`, `pff_hurry` o `pff_sack`. Es una etiqueta operativa para esta revisión, no una definición oficial de presión.

| Evento defensivo | Jugadas | Tasa de completos | Yardas promedio | Tasa de sack por `passResult` |
|---:|---:|---:|---:|---:|
| No | 5,341 | 65.3% | 8.15 | 0.0% |
| Sí | 3,216 | 35.2% | 3.94 | 16.9% |

La asociación es fuerte: las jugadas marcadas con presión/hit/sack tienen menos completos y menos yardas. No prueba que toda la diferencia sea causada por la línea; también intervienen el QB, la cobertura, el diseño, la profundidad del pase y el tiempo que tarda en lanzar.

Por número de rushers:

| Rushers | Jugadas | Evento defensivo | Sack | Completos | Yardas promedio |
|---:|---:|---:|---:|---:|---:|
| 3 | 420 | 24.5% | 4.0% | 56.0% | 7.26 |
| 4 | 6,011 | 35.1% | 5.7% | 55.1% | 6.53 |
| 5 | 1,689 | 46.7% | 8.9% | 51.2% | 6.49 |
| 6 | 348 | 48.9% | 5.7% | 48.0% | 6.90 |
| 7 | 69 | 65.2% | 10.1% | 44.9% | 4.48 |

Mandar más rushers se asocia con más eventos defensivos y menos completos, pero no hay una relación monotónica limpia en sacks o yardas. El contexto de la llamada importa. Comparar estos promedios sin ajustar por down, distancia, cobertura, marcador y rival sería engañoso.

Por tipo amplio de cobertura:

| Cobertura | Jugadas | Evento defensivo | Sack | Completos | Yardas promedio |
|---|---:|---:|---:|---:|---:|
| Man | 2,481 | 41.6% | 7.4% | 46.6% | 6.58 |
| Zone | 5,588 | 35.4% | 5.7% | 58.2% | 6.85 |
| Other | 488 | 42.0% | 7.0% | 44.1% | 3.22 |

`Other` agrupa Bracket, Goal Line, Miscellaneous, Prevent y Red Zone. Su promedio mezcla situaciones muy distintas y no debe interpretarse como una estrategia uniforme.

Play action:

| Play action | Jugadas | Evento defensivo | Sack | Completos | Yardas promedio | Rushers promedio | Defensores en caja |
|---:|---:|---:|---:|---:|---:|---:|---:|
| No | 6,519 | 37.2% | 6.3% | 53.8% | 6.17 | 4.23 | 5.79 |
| Sí | 2,038 | 38.8% | 6.2% | 54.8% | 7.83 | 4.32 | 6.76 |

Play action aparece con 1.66 yardas más por jugada, pero también con casi un defensor adicional en la caja. Esto es selección de situación, no evidencia causal de que play action agregue 1.66 yardas.

### 2.5 Coberturas: la taxonomía es internamente consistente

La relación observada es:

- `Man`: Cover-0, Cover-1 y 2-Man.
- `Zone`: Cover-2, Cover-3, Cover-6 y Quarters.
- `Other`: Bracket, Goal Line, Miscellaneous, Prevent y Red Zone.

Cada valor detallado cae en una sola categoría amplia. No hay cruces contradictorios.

### 2.6 Personal

- `personnelD` suma exactamente 11 jugadores en las 8,556 jugadas no nulas.
- `personnelO` normalmente enumera cinco jugadores de habilidad: 8,427 jugadas suman 5.
- Hay paquetes que incluyen `2 QB`, `6 OL` o `7 OL`; por eso algunas cadenas suman 6, 10 u 11 si se cuentan todos los números escritos.
- Tres cadenas `1 RB, 1 TE, 2 WR,1 LB` suman cuatro bajo el parser de posiciones ofensivas porque incluyen un LB. Son paquetes especiales, no necesariamente registros corruptos.
- Una jugada tiene `personnelO` y `personnelD` nulos.

No se debe deducir el número de jugadores en campo sumando ciegamente `personnelO`; hay que interpretar su convención.

### 2.7 Fechas

El README documenta `birthDate` como `YYYY-MM-DD`, pero 14 fechas no nulas usan `MM/DD/YYYY`. Ejemplos: `05/15/1986` y `07/10/1988`. Además hay 232 fechas nulas.

Una lectura estricta con un solo formato convertiría esas 14 fechas válidas en nulos. Para edades, se deben admitir ambos formatos de forma explícita y conservar una bandera de calidad.

### 2.8 Tracking y eventos

- Hay exactamente una fila del balón por jugada y cuadro.
- Hay etiqueta de snap manual o automática en 8,533 de 8,557 jugadas; faltan 24.
- Hay etiqueta de pase hacia adelante en 7,604 jugadas.
- Hay 543 sacks y 449 scrambles en `passResult`; por eso muchas jugadas de esos tipos no tienen `pass_forward`.
- En pases completos, incompletos e interceptados hay 7,565 jugadas y 7,562 etiquetas de pase. Las pequeñas diferencias y los eventos de pase en algunos sacks/scrambles requieren reglas explícitas.
- Con snap y pase disponibles, el tiempo de lanzamiento es `(frame_throw - frame_snap) / 10`. Hay 7,583 valores válidos, media 2.96 s, mediana cercana a 2.7 s y máximo 9.8 s.
- No hubo un pase marcado antes o en el mismo cuadro que el snap.
- Las etiquetas de llegada o resultado de pase solo permiten ubicar 579 jugadas con el conjunto de nombres revisado. No basta con buscar `pass_arrived`; para separación en el punto de llegada hará falta una regla adicional y validarla.

La división por 10 ya no es una hipótesis: NFL Football Operations informa que Next Gen Stats captura posición, velocidad y aceleración [10 veces por segundo](https://operations.nfl.com/gameday/technology/nfl-next-gen-stats/).

### 2.9 Coordenadas y extremos

- En el snap, la coordenada `x` del balón y `absoluteYardlineNumber` difieren en promedio 0.54 yardas al priorizar la etiqueta manual. El 84.1% queda a una yarda o menos; el máximo es 7.66.
- `absoluteYardlineNumber` es una buena referencia aproximada de la línea de golpeo, pero no una igualdad exacta cuadro a cuadro.
- Fuera del rango documentado: 112 filas de jugador en `x`, 857 en `y`; 0 filas del balón en `x` y 204 en `y`.
- Ningún jugador supera 15 yardas/s; el balón sí lo hace en 29,394 filas.
- Solo 10 filas de jugador superan 15 yardas/s² de aceleración; el balón lo hace en 1,835.

Esto corrige una duda del diagnóstico inicial: los máximos globales de velocidad y casi todos los extremos altos de aceleración provienen del balón. Aun así, las 10 aceleraciones de jugador mayores a 15 merecen inspección antes de usarlas.

## 3. Posibles problemas y tratamiento recomendado

| Problema | Riesgo | Tratamiento |
|---|---|---|
| Solo semanas 1–8 de 2021 | Muestra corta; lesiones, rivales y calendario sesgan rankings | Reportar intervalos y mínimos de snaps; evitar afirmar calidad permanente |
| Selección de jugadas | El conjunto está centrado en dropbacks; `dropBackType` incluye 5 `DESIGNED_RUN` | Describirlo como muestra de juego aéreo/dropbacks, no como todas las jugadas NFL |
| `event` incompleto | Faltan 24 snaps y muchas etiquetas de lanzamiento/llegada | Implementar respaldo controlado y excluir/etiquetar casos sin evento |
| Evento manual vs `autoevent_*` | Elegir el primero puede mover el inicio y duplicar conceptos | Priorizar manual; usar automático solo como respaldo; guardar fuente del evento |
| Fechas en dos formatos | Edades nulas o incorrectas | Parsear `%Y-%m-%d` y luego `%m/%d/%Y` |
| Nulos PFF condicionados por rol | Promedios falsos al tratar nulo como cero globalmente | Filtrar por roles aplicables antes de llenar nulos |
| Marca defensiva y cargo ofensivo no coinciden | Una sola etiqueta de “presión” mezcla criterios | Mantener ambas variables separadas y validar con tracking/video |
| Yardas incluyen penalizaciones | Confunde desempeño de la jugada con aplicación de reglas | Analizar `prePenaltyPlayResult` y faltas por separado |
| `personnelO` no es un conteo simple | Paquetes especiales parecen inválidos | Parsear posiciones y conservar la cadena original |
| Dirección de juego | Coordenadas incomparables izquierda/derecha | Normalizar para que la ofensiva ataque siempre al mismo lado |
| Coordenadas fuera del campo | Distancias y áreas pueden sesgarse | No recortar automáticamente; marcar y decidir según la pregunta |
| Nombres repetidos | Uniones incorrectas | Usar `nflId`, no `displayName` |
| No hay EPA, air yards, ruta ni receptor objetivo explícitos | Yardas y completos no separan dificultad y valor | Derivar con cautela o añadir play-by-play público vía llaves documentadas |
| `pff_nflIdBlockedPlayer` indica el primer defensor bloqueado | No representa cambios, stunts o dobles dinámicos | Reconstruir asignaciones por cuadro con tracking |

## 4. Conclusiones que sí podemos sacar

1. **La integridad relacional es alta.** Las tablas encajan sin registros huérfanos en las llaves principales.
2. **PFF da roles completos por jugada.** Podemos separar QB, bloqueadores, rutas, rushers y cobertura para los 22 jugadores.
3. **La muestra es apropiada para estudiar protección, pass rush y cobertura en dropbacks.** No es apropiada para evaluar el juego terrestre completo.
4. **La presión registrada se asocia con peores resultados ofensivos.** En esta muestra, la tasa de completos baja de 65.3% a 35.2% cuando existe una marca defensiva de hit/hurry/sack.
5. **Más rushers elevan la frecuencia de eventos defensivos en el agregado, pero tienen un costo de cobertura que no aparece en una tasa simple.** Hay que medir ambos lados de la decisión.
6. **Play action aparece en contextos defensivos distintos.** Tiene más yardas, pero también más defensores en caja; el promedio sin ajuste no identifica su efecto.
7. **`frameId` permite tiempos en décimas de segundo.** La frecuencia de 10 Hz está confirmada por la NFL.
8. **Los valores extremos globales de movimiento mezclan jugadores y balón.** Deben separarse antes de cualquier control de calidad.

## 5. Conclusiones que todavía no podemos sacar

1. No sabemos si mandar cinco rushers **causa** más presión o mejora el valor esperado de la defensa. Down, distancia, cobertura, rival y situación cambian la decisión.
2. No podemos nombrar al “mejor” liniero o pass rusher solo con tasas crudas. Faltan ajuste por rival, dobles equipos, lado, tiempo de lanzamiento y tamaño de muestra.
3. No sabemos si una presión fue culpa de un bloqueador, del QB por sostener el balón o de receptores que no se separaron.
4. No podemos medir bien separación en el punto de recepción hasta definir un final de trayectoria confiable para las jugadas sin `pass_arrived`.
5. No podemos evaluar si una decisión fue buena con yardas únicamente. Hace falta EPA, probabilidad de conversión o probabilidad de victoria.
6. No conocemos la asignación de cobertura individual, la ruta ni el receptor objetivo de forma explícita.
7. No podemos generalizar de ocho semanas de 2021 a otras temporadas sin validación externa.
8. No se verificó por video la precisión de PFF ni de los eventos de tracking.

## 6. Qué ya existe públicamente

- [NFL Next Gen Stats](https://operations.nfl.com/gameday/technology/nfl-next-gen-stats/) usa tracking para métricas de rendimiento, clasificación de formaciones/coberturas/rutas y medidas avanzadas como probabilidad de completar. También confirma los 10 registros por segundo.
- La NFL y AWS publicaron [Pressure Probability](https://www.nfl.com/news/next-gen-stats-introduction-to-pressure-probability), que identifica roles, estima presión cada décima de segundo y reconstruye enfrentamientos bloqueador–rusher, dobles ayudas y tiempo hasta presión. Este dataset fue precisamente el tipo de material que impulsó esa línea de trabajo.
- [ESPN Pass Block Win Rate y Pass Rush Win Rate](https://africa.espn.com/nfl/story/_/id/24892208/creating-better-nfl-pass-blocking-pass-rushing-stats-analytics-explainer-faq-how-work) evalúan si un bloqueo se sostiene durante 2.5 segundos y usan posición, proximidad y orientación para inferir enfrentamientos. ESPN advierte que presión o tiempo en bolsa, aislados, pueden confundir desempeño de línea con decisiones del QB y cobertura.
- La [clasificación de coberturas de Next Gen Stats](https://www.nfl.com/news/next-gen-stats-new-advanced-metrics-you-need-to-know-for-the-2022-nfl-season) ya automatiza man/zone y coberturas específicas con tracking. Por tanto, “clasificar Cover-1 vs Cover-3” por sí solo no sería novedoso.
- [PFF](https://www.pff.com/news/pro-pffs-signature-stat-series) comercializa calificaciones y estadísticas de eficiencia de protección basadas en sacks, hits, hurries y snaps de bloqueo. En nuestros archivos ya tenemos varias de esas anotaciones base.
- [SūmerSports](https://sumersports.com/solutions/nfl) ofrece herramientas de scouting, roster y decisión para equipos, y presenta análisis filtrables por contexto. Su sitio no permite verificar algoritmos ni cobertura exacta desde estos datos, pero confirma que el producto final importa tanto como la métrica.

Estas referencias muestran que otra tasa global de presión, una clasificación básica de cobertura o un ranking de linieros tendría poca diferenciación. No prueban que ninguna organización haya construido exactamente las propuestas siguientes; no es posible demostrar novedad mundial solo con fuentes públicas.

## 7. Preguntas prioritarias desde la perspectiva de un entrenador

### Prioridad 1: ¿Por qué se rompió la protección y cuándo?

**Pregunta de entrenador:** “¿La presión vino por derrota física, asignación equivocada, stunt mal entregado, free rusher o porque el QB sostuvo el balón?”

**Cómo ayudan los datos:**

1. PFF identifica bloqueadores, rushers, primer oponente bloqueado y cargos de presión.
2. Tracking permite reconstruir distancias, orientación y cambio de emparejamiento cada 0.1 s.
3. `ball_snap` y `pass_forward` delimitan el intervalo relevante.
4. Formación, personal y `dropBackType` dan contexto al diseño.

**Salida útil:** una tarjeta por jugada con “primer quiebre”, jugador responsable probable, tipo de quiebre, tiempo y evidencia. Para un coach es más accionable que un ranking anual.

**Qué falta:** validar contra video y definir reglas para cambios de asignación, chips, dobles y QBs que salen de la bolsa.

### Prioridad 2: ¿El blitz produjo valor suficiente para el espacio que sacrificó?

**Pregunta de entrenador:** “Cuando mando cinco o más, ¿llego antes de que el QB encuentre el hueco que abrí?”

**Cómo ayudan los datos:**

- Número de `Pass Rush` mide recursos enviados.
- Tracking mide tiempo y distancia de los rushers al QB.
- `Coverage`, tipo de cobertura y separación espacial miden el costo detrás.
- `passResult` y yardas dan un resultado básico.

**Salida útil:** una frontera riesgo–recompensa por llamada y situación: probabilidad/tiempo de presión frente al espacio concedido y al resultado.

**Por qué es prometedora:** Pressure Probability ya mide llegar al QB; el diferenciador sería unir explícitamente ese beneficio con el “impuesto de cobertura” de sacar un defensor.

### Prioridad 3: ¿Qué protección falla contra stunts y cambios de asignación?

**Pregunta de entrenador:** “¿Qué parejas de OL intercambian bien los rushers y cuáles pierden comunicación?”

**Cómo ayudan los datos:**

- Se puede inferir el rusher atendido por cada bloqueador en cada cuadro.
- Los cambios bruscos de emparejamiento permiten detectar entregas y posibles stunts.
- PFF aporta el primer defensor bloqueado y quién permitió hurry/hit/sack.

**Salida útil:** matriz por pareja de linieros y tipo de intercambio, con tiempo hasta pérdida y ejemplos de jugadas.

**Posible innovación:** pasar de “quién perdió” a “dónde falló la coordinación de la unidad”. Las métricas públicas citadas reconocen matchups y dobles; una herramienta centrada en la entrega entre dos bloqueadores sería más específica para enseñanza.

### Prioridad 4: ¿El QB convierte protección en tiempo útil?

**Pregunta de entrenador:** “¿Lanza rápido porque leyó bien, o abandona una bolsa limpia? ¿Crea él mismo parte de la presión?”

**Cómo ayudan los datos:**

- Tiempo snap–pase.
- Geometría de la bolsa a partir de los bloqueadores.
- Movimiento del QB respecto de la bolsa y rushers.
- Cobertura, resultado y separación potencial de receptores.

**Salida útil:** separar “tiempo disponible” de “tiempo utilizado”, por QB, concepto y cobertura.

**Advertencia:** no hay progresión de lecturas ni ruta explícita. La etiqueta debe ser probabilística y no presentarse como intención cierta.

### Prioridad 5: ¿Cuándo play action realmente desplaza a la defensa?

**Pregunta de entrenador:** “¿Qué linebackers o estructuras reaccionan a la finta, cuánto espacio crea y contra qué coberturas?”

**Cómo ayudan los datos:**

- `pff_playAction` identifica la finta.
- Tracking mide el primer paso de linebackers y safeties respecto de la línea.
- `defendersInBox`, cobertura, formación y personal controlan el contexto.
- La separación posterior y las yardas miden el posible beneficio.

**Salida útil:** desplazamiento defensivo inducido en las primeras décimas y espacio creado, no solo yardas promedio de play action.

### Prioridad 6: ¿Qué cobertura mostramos antes del snap y cuál jugamos después?

**Pregunta de entrenador:** “¿Disfrazamos bien sin llegar tarde a nuestra responsabilidad?”

**Cómo ayudan los datos:**

- Posiciones y orientaciones pre-snap permiten resumir la estructura aparente.
- La etiqueta PFF da la cobertura final.
- Trayectorias de safeties/corners muestran rotación y tiempo para llegar a su zona.

**Salida útil:** índice de disfraz y costo de recuperación por llamada. Esto complementa una clasificación de cobertura existente en lugar de repetirla.

## 8. Propuesta con mayor valor e innovación

La propuesta más defendible es un **diagnóstico causal-operativo de presión**, presentado como herramienta de coaching:

> Para cada dropback, separar presión por derrota individual, error de asignación/intercambio, rusher libre, cobertura prolongada o movimiento/retención del QB; medir cuándo ocurre y mostrar la evidencia espacial.

### Por qué elegirla

- Usa las cinco tablas y explota las etiquetas PFF que ya vienen en los datos.
- Responde “por qué” y “qué corregir”, no solo “cuánto”.
- Evita competir directamente con Pressure Probability o PBWR/PRWR, que ya existen.
- Puede producir un hallazgo principal aun sin IA generativa.
- Permite una aplicación clara: filtro por equipo, jugador, tipo de protección, número de rushers y situación; después muestra jugadas representativas y agregados con tamaño de muestra.

### MVP analítico sugerido

1. Normalizar coordenadas según `playDirection`.
2. Elegir snap y pase priorizando eventos manuales.
3. Identificar QB, bloqueadores y rushers con PFF.
4. Construir por cuadro las distancias rusher–QB y bloqueador–rusher.
5. Detectar primer cambio de ventaja y cambios de asignación.
6. Etiquetar heurísticamente: derrota, free rusher, posible stunt/entrega, cobertura prolongada o escape del QB.
7. Validar una muestra de cada clase contra descripción y, si está disponible, video.
8. Relacionar la etiqueta con hurry/hit/sack y resultado, sin llamar causal a una asociación no validada.

## 9. Datos adicionales que mejorarían el proyecto

- Play-by-play de nflverse para EPA, first-down probability, win probability, air yards, sacks anulados y situación detallada. El README documenta el cruce `gameId → old_game_id` y `playId → play_id`.
- Video All-22 para validar asignaciones, rutas, stunts y receptor objetivo.
- Más semanas/temporadas para estabilidad y validación temporal.
- Ruta, receptor objetivo y profundidad del pase para separar cobertura de ejecución del QB.
- Lesiones y alineaciones para interpretar cambios de unidad.
- Llamada exacta de protección, que probablemente no es pública; sin ella solo se puede inferir responsabilidad.

## 10. Decisión recomendada

La siguiente fase debería empezar por **protección y origen de la presión**, con el blitz como primer corte táctico. Antes de modelar, conviene construir una tabla a nivel jugada con:

```text
gameId, playId, offense, defense, QB,
pass_rushers, pass_blockers, coverage,
play_action, dropback_type, time_to_throw,
first_pressure_or_advantage_frame,
pressure_source_candidate, passResult,
prePenaltyPlayResult, playResult
```

Después se validan manualmente casos de cada etiqueta. Si esa validación falla, la alternativa más segura es limitar el producto a métricas observables: tiempo de lanzamiento, distancia mínima al QB, número de rushers, presión PFF y resultado.

---

### Nota sobre fuentes web

El contenido de las fuentes enlazadas fue resumido y reformulado para respetar sus restricciones de licencia; no se reprodujeron pasajes extensos. La investigación pública permite comparar enfoques, pero no conocer herramientas privadas de los 32 equipos ni probar novedad absoluta.
