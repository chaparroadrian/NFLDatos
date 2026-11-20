# Diagnóstico inicial del dataset

Fuente: `data/nfl-big-data-bowl-regional-event-data-main/` (NFL Big Data Bowl, regional). Todo lo de abajo viene de leer los archivos con pandas en modo solo lectura; los originales no se modificaron. Los 122 archivos de tracking se leyeron uno por uno y solo se guardaron agregados, no se cargaron juntos. No se hicieron gráficas ni modelos.

Las definiciones de columnas provienen del `README.md` incluido. Donde algo es mi interpretación y no un hecho verificado, lo marco como **(hipótesis)**.

## 1. Archivos y formatos

| Archivo | Formato | Tamaño | Contenido |
|---|---|---|---|
| `README.md` | Markdown | 12 KB | Documentación oficial de variables y llaves |
| `data/games.csv` | CSV | 6.7 KB | Un renglón por partido |
| `data/plays.csv` | CSV | 2.3 MB | Un renglón por jugada |
| `data/players.csv` | CSV | 104 KB | Un renglón por jugador |
| `data/pffScoutingData.csv` | CSV | 13 MB | Un renglón por jugador en cada jugada (datos de PFF) |
| `data/tracking/tracking_<gameId>.csv` | CSV (122 archivos) | ~800 MB en total | Posición de jugadores y balón, cuadro por cuadro |

Todos son CSV con encabezado. Los valores faltantes aparecen como `NA` en `plays`, `players` y `pffScoutingData`. En tracking, `nflId`, `o` y `dir` van como `NA` en las filas del balón. La columna `event` usa la cadena literal `None` en los cuadros sin evento (pandas la lee como nulo por defecto).

Los datos son de la temporada 2021, semanas 1 a 8 (`games.csv`: `season` tiene un solo valor, 2021, y `week` va de 1 a 8).

## 2. Dimensiones

| Tabla | Filas | Columnas |
|---|---|---|
| games | 122 | 7 |
| plays | 8,557 | 32 |
| players | 1,679 | 7 |
| pffScoutingData | 188,254 | 15 |
| tracking (122 archivos sumados) | 8,314,178 | 16 |

Partidos por semana: S1 16, S2 16, S3 16, S4 16, S5 16, S6 14, S7 13, S8 15. Hay 32 equipos. Promedio de 70 jugadas por partido (mín 47, máx 97).

## 3. Variables, tipos y faltantes

### games (sin faltantes ni duplicados)
`gameId` int, `season` int, `week` int, `gameDate` texto (`mm/dd/yyyy`), `gameTimeEastern` texto (`HH:MM:SS`), `homeTeamAbbr` texto, `visitorTeamAbbr` texto.

### plays
| Variable | Tipo | Faltantes |
|---|---|---|
| gameId, playId | int | 0 |
| playDescription | texto | 0 |
| quarter, down, yardsToGo, yardlineNumber, preSnapHomeScore, preSnapVisitorScore, prePenaltyPlayResult, playResult, pff_playAction | int | 0 |
| possessionTeam, defensiveTeam, gameClock (`MM:SS`), passResult, pff_passCoverage, pff_passCoverageType | texto | 0 |
| yardlineSide | texto | 125 (1.5%) |
| penaltyYards | float | 7,801 (91.2%) |
| foulName1 / foulNFLId1 | texto / float | 7,821 (91.4%) |
| foulName2 / foulNFLId2 | texto / float | 8,527 (99.6%) |
| foulName3 / foulNFLId3 | texto / float | 8,556 (100%, solo 1 dato) |
| absoluteYardlineNumber | float | 1 |
| offenseFormation | texto | 7 |
| personnelO, personnelD | texto | 1 cada una |
| defendersInBox | float | 7 |
| dropBackType | texto | 528 (6.2%) |

### players
`nflId` int, `height` texto (formato `pies-pulgadas`, p. ej. `6-4`), `weight` int, `birthDate` texto (`YYYY-MM-DD`), `collegeName` texto, `officialPosition` texto, `displayName` texto. Faltantes: `birthDate` 232 (13.8%), `collegeName` 224 (13.3%). El resto está completo.

### pffScoutingData
`gameId`, `playId`, `nflId` int. `pff_role`, `pff_positionLinedUp`, `pff_blockType` texto. El resto son indicadores 0/1 guardados como float (por los nulos): `pff_hit`, `pff_hurry`, `pff_sack`, `pff_beatenByDefender`, `pff_hitAllowed`, `pff_hurryAllowed`, `pff_sackAllowed`, `pff_backFieldBlock`. `pff_nflIdBlockedPlayer` es float.

Los nulos aquí **no son datos perdidos**, son "no aplica" según el rol:
- `pff_hit/hurry/sack`: nulos en 50% de los renglones. Solo se llenan para `Coverage` y `Pass Rush` (100% de esos roles tiene valor; 0% en los demás).
- `pff_blockType` y los indicadores de bloqueo: se llenan en todos los `Pass Block` (100%) y en 5% de los `Pass Route`.
- Si se promedia o cuenta sin filtrar por rol, los resultados se distorsionan.

### tracking
Todos los archivos tienen el mismo esquema: `gameId`, `playId`, `nflId` (float por los nulos), `frameId` int, `time` texto ISO, `jerseyNumber` float, `team` texto, `playDirection` texto (`left`/`right`), `x`, `y`, `s`, `a`, `dis`, `o`, `dir` float, `event` texto.

Faltantes: 361,486 filas sin `nflId`, `jerseyNumber`, `o` y `dir`. Corresponden al balón (`team = football`), una fila por cuadro. `event` es nulo en 7,673,352 filas (92%): solo se marca en cuadros clave.

## 4. Duplicados

- Renglones completos duplicados: 0 en games, plays, players y pffScoutingData.
- Llaves duplicadas: 0 en `(gameId, playId)` de plays, 0 en `nflId` de players, 0 en `(gameId, playId, nflId)` de pff, 0 en `(gameId, playId, nflId, frameId)` de tracking.
- `playDescription` se repite en 4 jugadas (2 pares, ambos conversiones de 2 puntos con el mismo texto). Son jugadas distintas por `playId`; no son duplicados reales.
- `displayName` se repite en 8 casos con distinto `nflId` (por ejemplo, dos "A.J. Green": un WR y un CB). Son personas distintas. **Conviene unir siempre por `nflId`, nunca por nombre.**

## 5. Relaciones entre archivos

```
games (gameId) 1──N plays (gameId, playId) 1──N pffScoutingData (gameId, playId, nflId) N──1 players (nflId)
                          │
                          └─1──N tracking (gameId, playId, nflId, frameId)   [nflId nulo = balón]
```

Verificado:
- Las 8,557 jugadas de `plays` coinciden exactamente con las 8,557 jugadas encontradas en tracking. No sobra ni falta ninguna. Todas las de `pffScoutingData` también están en `plays`, y viceversa.
- Todos los `gameId` de plays existen en games. El `gameId` dentro de cada archivo de tracking coincide con el nombre del archivo.
- Los 1,679 `nflId` de pff y de tracking son los mismos 1,679 de `players`. Ninguno queda sin pareja.
- Los `nflId` que aparecen en `pff_nflIdBlockedPlayer` y en `foulNFLId1/2/3` también existen en players.
- Cada jugada tiene exactamente 22 jugadores en pff y 22 `nflId` distintos en tracking, más el balón.
- `possessionTeam` y `defensiveTeam` nunca coinciden entre sí, y la posesión siempre es de uno de los dos equipos del partido.
- Según el README, `gameId` y `playId` se pueden cruzar con `old_game_id` y `play_id` del play-by-play de nflverse (no verificado aquí, no se descargó nada).

## 6. Hallazgos importantes y posibles inconsistencias

1. **El dataset contiene solo jugadas de pase (dropbacks).** `passResult` nunca es nulo y toma los valores C (4,620), I (2,755), S (543), R (449) e IN (190). No hay jugadas terrestres planeadas. Esto limita las preguntas que se pueden contestar sobre carreras. Lo concluyo del contenido de `passResult`; el README no lo dice de forma explícita.
2. **`down = 0` en 35 jugadas** (valor fuera de 1–4). Las revisadas son intentos de conversión de 2 puntos (`yardsToGo = 0`). **Hipótesis:** las 35 son conversiones de 2 puntos; solo leí las descripciones de las primeras 4.
3. **`quarter = 5` en 98 jugadas:** probablemente tiempo extra. Es un valor válido, pero hay que decidir cómo tratarlo.
4. **`playResult` vs `prePenaltyPlayResult`:** en 253 jugadas `playResult - prePenaltyPlayResult` no es igual a `penaltyYards` (con nulo = 0). Ejemplo: playResult 11, prePenalty 8, penaltyYards 26 (pase interferencia defensiva: el resultado se define por la regla de la falta, no por la suma). La relación entre las tres columnas no es una suma simple; hay que revisar antes de usarlas.
5. **`penaltyYards` y `foulName1` no siempre van juntos:** 20 jugadas tienen `penaltyYards` sin `foulName1` (por las descripciones vistas, son penalizaciones declinadas con 0 yardas, o falta sin nombre). El valor 0.0 en `penaltyYards` significa algo distinto a nulo. Las 20 no se revisaron una por una.
6. **`yardlineSide` nulo en 125 jugadas:** todas con `yardlineNumber = 50`, es decir, la media cancha, donde no hay lado. No es un error.
7. **Una jugada** (`gameId 2021091904`, `playId 3676`) no tiene `absoluteYardlineNumber`, `personnelO` ni `personnelD`.
8. **`dropBackType` nulo en 528 jugadas** (6.2%). Es más frecuente en pases incompletos (11%) que en completos (3%). **Hipótesis:** PFF no lo clasificó en algunas jugadas, pero no se sabe por qué.
9. **Capitalización distinta entre README y datos:** el README dice `Pass block` / `Pass route` / `Pass rush`; los datos traen `Pass Block` / `Pass Route` / `Pass Rush`. Filtrar con el texto del README devolvería cero filas.
10. **Sacks:** `passResult = S` en 543 jugadas; `pff_sack = 1` en 602 renglones (jugador) que caen en 536 jugadas, todas con `passResult = S`. Hay más renglones que jugadas porque varios defensores pueden compartir crédito. Hay 7 jugadas con sack según `passResult` pero sin `pff_sack` (no investigado el motivo).
11. **Cobertura:** `Red Zone` aparece 376 veces, `Cover-0` 270 y `Goal Line` 25. Algunas categorías (Miscellaneous 8, Bracket 47) tienen pocas observaciones.
12. **Posiciones:** `officialPosition` incluye `LB` (2) y `DB` (2), categorías genéricas junto a las específicas (OLB, ILB, CB, FS...). `pff_positionLinedUp` tiene 56 valores, más detallados que la posición oficial.
13. **Jugadores sin fecha de nacimiento (232) y universidad (224):** concentrados en CB, WR, OLB, T, DE (los 5 más frecuentes entre los que no tienen fecha). No hay un patrón claro por posición más allá de lo que pesa cada posición.

### Calidad del tracking
- **Resolución de tiempo:** en la muestra revisada (una jugada), los cuadros consecutivos tienen `time` con la misma marca o con 1 segundo de diferencia (34 y 4 casos respectivamente). Es decir, `time` solo tiene precisión de segundos. **No sirve para calcular tiempos entre cuadros; usar `frameId`.** Si la frecuencia es 10 cuadros/s (lo habitual en NGS, no lo confirma el README), el número de cuadros es el reloj correcto.
- **Valores fuera del campo:** `x` va de -3.55 a 121.15 (el rango documentado es 0–120) e `y` de -4.53 a 57.72 (documentado 0–53.3). Jugadores o balón fuera de los límites, normal en jugadas que salen de la cancha, pero hay que decidir si se filtran.
- `a` llega a 50.69 yardas/s² y `s` a 29.34 yardas/s. La aceleración máxima es muy alta para un humano **(hipótesis: ruido del sensor o balón en pase; no se verificó si pertenece a jugadores o al balón)**.
- `frameId`: mínimo 1, máximo 203. El promedio de cuadros por jugada, calculado por partido, va de 26 a 48 aproximadamente; la jugada más larga tiene 203 cuadros.
- Los eventos están muy desbalanceados. `ball_snap` (196,236 filas) y `autoevent_ballsnap` (86,641) son dos variantes del evento de snap (el prefijo `auto` sugiere una marca automática; el README no lo explica). Lo mismo ocurre con `pass_forward` (173,604) y `autoevent_passforward` (85,882). Un solo evento ocupa varias filas porque se repite en los 23 objetos de cada cuadro (22 jugadores + balón). **Para ubicar un evento en una jugada, hay que usar un único `nflId` o el balón, no contar filas.** No verifiqué si algunas jugadas traen a la vez la versión manual y la `auto`.
- `playDirection` está balanceado (izquierda 4.29 M filas, derecha 4.03 M). Las coordenadas **no** están normalizadas al sentido del ataque; habrá que voltear `x` e `y` para comparar jugadas.

## 7. Qué se puede hacer con estos datos

Cada jugada permite combinar tres capas: contexto (plays), roles/resultados individuales (PFF) y movimiento (tracking). Eso la hace una base fuerte para análisis de **juego aéreo, protección del mariscal y cobertura defensiva**, y débil para preguntas sobre carreras o patadas.

## 8. Preguntas posibles

Conectan con lo que los datos realmente tienen:

**Protección y presión (plays + PFF + tracking)**
1. ¿Qué tan rápido gana un pass rusher a su bloqueador (distancia al QB por cuadro desde el snap) y cómo se relaciona con hurry/hit/sack?
2. ¿El tipo de bloqueo (`pff_blockType`: PP, PA, PR, SW...) o la formación cambian la probabilidad de que el bloqueador sea vencido (`pff_beatenByDefender`, `pff_hurryAllowed`)?
3. ¿Cuántos rushers vs. bloqueadores se enfrentan y cuándo el rush de 4 basta frente a blitz?
4. ¿Hay diferencias de presión por posición alineada (`pff_positionLinedUp`, LEO/REO vs. DLT/DRT) o por equipo?

**Cobertura defensiva**
5. ¿Qué tan bien funciona cada cobertura (`pff_passCoverage`, `Man/Zone`) en yardas, completos e intercepciones? ¿Cambia por down y distancia?
6. ¿Cuánto espacio deja un defensor al receptor en `pass_forward` y `pass_arrived`, y qué tan predictiva es esa separación del resultado?
7. ¿Se puede detectar si el defensor realmente jugó man o zona usando tracking y compararlo con la etiqueta de PFF?
8. ¿Cuánto se mueve la defensa tras el snap (rotación de safeties) frente a lo que muestra el pre-snap?

**Ofensiva y contexto**
9. ¿El play action (`pff_playAction`) mejora los yardas en pases según la cobertura o la cantidad de defensores en la caja (`defendersInBox`)?
10. ¿Cómo cambia la ofensiva (formación, personal, tipo de dropback) según marcador, cuarto y down?
11. ¿El movimiento antes del snap (`man_in_motion`, `shift`) altera el éxito del pase o la cobertura que muestra la defensa?
12. ¿Cuánto tarda el QB en lanzar (cuadros entre `ball_snap` y `pass_forward`) y cómo se asocia con presión, sack o profundidad del pase?

**Penalizaciones**
13. ¿Qué faltas aparecen más (DPI, holding) y bajo qué cobertura o presión ocurren?

**Datos externos (permitidos por el README)**
14. Con nflverse (`old_game_id`, `play_id`) se pueden añadir EPA y probabilidad de victoria para medir el valor de cada jugada, en lugar de solo yardas.

## 9. Recomendaciones antes de analizar

- Unir siempre por `nflId`, `gameId` y `playId`; nunca por nombre.
- Leer tracking por partido o por jugada, filtrando columnas, porque son 8.3 M de filas.
- Filtrar `pff_*` por rol antes de calcular tasas.
- Normalizar el sentido de ataque (`playDirection`) antes de comparar coordenadas.
- Usar `frameId` y no `time` para medir tiempos.
- Decidir de antemano qué hacer con `down = 0` (conversiones de 2 puntos) y `quarter = 5`.
- Cuidado con los datos del README: el texto de `pff_role` difiere en mayúsculas.

## 10. Lo que no se pudo comprobar

- La frecuencia real de muestreo del tracking (el README no la indica).
- El significado exacto de las 253 diferencias entre `playResult`, `prePenaltyPlayResult` y `penaltyYards`.
- Si los valores extremos de aceleración corresponden al balón o a jugadores.
- La causa de los nulos en `dropBackType` y los 7 sacks sin `pff_sack`.
- La coincidencia con nflverse (no se descargó).
