# Requirements Document

## Introduction

PocketIQ ("¿Cómo nos va a atacar esta defensa?") es una aplicación web para que un entrenador ofensivo estudie las tendencias de presión de un rival defensivo, entienda por dónde y cuándo entra la presión y compare las respuestas de protección observadas. La aplicación usa los datos del NFL Big Data Bowl (temporada 2021, semanas 1 a 8): contexto de jugada, etiquetas de PFF y tracking cuadro por cuadro.

La aplicación debe responder preguntas como: "En tercera y larga, con cinco bloqueadores y formación shotgun, ¿con qué frecuencia manda cinco o más rushers esta defensa, por dónde entra la amenaza, cuánto tarda en aparecer y qué protecciones se asocian con mejores resultados?".

Toda métrica mostrada se clasifica en una de cuatro fuentes: variable observada, etiqueta PFF, inferencia heurística o resultado con muestra insuficiente. Ninguna inferencia se presenta como asignación confirmada por el equipo o por video.

El stack, la estructura de carpetas y el contrato de despliegue siguen `.kiro/steering/rules.md`: FastAPI en `backend/`, React + Vite + Tailwind 3 + Recharts en `dashboard/`, sin dependencias nuevas, datos de solo lectura y servidor efímero.

### Supuestos

1. **Rutas de datos.** Las instrucciones originales mencionan `data/nfl-big-data-bowl-regional-event-data-main/data/...`. En el espacio de trabajo los archivos están en `data/games.csv`, `data/plays.csv`, `data/players.csv`, `data/pffScoutingData.csv` y `data/tracking/tracking_<gameId>.csv` (122 archivos, 8,314,178 filas). Se usan estas rutas reales, relativas a la raíz del proyecto.
2. **Documento de verificación.** Las instrucciones mencionan `verificacion_datos.md`, que no existe. La fuente de hechos verificados es `diagnostico_inicial.md`, complementada con estos hechos aportados durante la preparación: todas las jugadas son dropbacks de pase; cada jugada tiene 22 jugadores en PFF; cada cuadro de tracking tiene 23 filas (22 jugadores y el balón); el tracking se muestrea a 10 cuadros por segundo; la columna `event` usa la cadena literal `"None"` en cuadros sin evento; 24 jugadas no tienen evento de snap; 3,746 jugadas tienen más de un cuadro marcado como snap; los valores de `pff_role` vienen capitalizados (`"Pass Block"`, `"Pass Route"`, `"Pass Rush"`, `"Pass"`, `"Coverage"`); 35 jugadas tienen `down == 0` (conversiones de dos puntos); `yardlineSide` es nulo cuando `yardlineNumber == 50`.
3. **Código existente.** `backend/main.py` contiene solo `GET /health`. `dashboard/` contiene un andamiaje de Vite + React (`src/App.tsx`, `src/main.tsx`, `src/index.css`) y `vite.config.ts` con `base: './'` y sin proxy. La implementación extiende estos archivos y crea `backend/analytics.py` y `backend/schemas.py`.
4. **Varios cuadros de snap.** Cuando una jugada tiene más de un cuadro con el evento de snap elegido, se toma el primer cuadro (menor `frameId`) de ese evento. Este criterio es un supuesto del documento y se puede revisar en el diseño.
5. **Umbrales contextuales.** Los umbrales "timeToThrow alto respecto de comparables" y "amenaza tras umbral contextual" (Requisito 12) se fijarán en el diseño a partir de percentiles de la muestra filtrada; este documento solo exige que sean deterministas y documentados.

## Glossary

- **PocketIQ**: La aplicación web completa (Backend más Dashboard) servida desde una sola URL y puerto.
- **Backend**: Aplicación FastAPI definida en `backend/main.py`, que expone `app`, `GET /health`, la API bajo `/api/...` y sirve el build de `dashboard/dist`.
- **Motor_Analitico**: Módulo `backend/analytics.py` que carga los datos, construye la Tabla_Analitica y calcula métricas, diagnósticos y resúmenes.
- **Esquemas**: Módulo `backend/schemas.py` con los modelos Pydantic de entrada y salida de la API.
- **Dashboard**: Aplicación React en `dashboard/src/`, compilada con `npm run build` hacia `dashboard/dist`.
- **Cache_Tracking**: Almacén en memoria del Motor_Analitico con agregados de tracking por rival defensivo y resultados por combinación de filtros.
- **Validador_Datos**: Conjunto de comprobaciones del Motor_Analitico que verifican la integridad de los datos al cargar y al procesar tracking.
- **Generador_Resumen**: Función del Motor_Analitico que produce el texto del resumen ejecutivo con una plantilla determinista.
- **Mapa_Presion**: Componente SVG del Dashboard que muestra los cinco Sectores de entrada.
- **Suite_Pruebas**: Pruebas automatizadas con pytest y httpx en el repositorio.
- **Tabla_Analitica**: Tabla en memoria con una fila por jugada (`gameId`, `playId`) y las columnas definidas en el Requisito 4.
- **Rival**: Equipo defensivo (`defensiveTeam`) que el usuario analiza.
- **Rusher**: Jugador con `pff_role == "Pass Rush"` en una jugada.
- **Bloqueador**: Jugador con `pff_role == "Pass Block"` en una jugada.
- **Ayuda_Chip**: Jugador con `pff_role == "Pass Route"` que tiene `pff_blockType` o `pff_nflIdBlockedPlayer` no nulo; se identifica como posible chip o ayuda antes de ruta y no cuenta como Bloqueador.
- **QB**: Jugador con `pff_role == "Pass"` en una jugada.
- **Blitz_Aproximado**: Jugada con `passRushers >= 5`.
- **Evento_Defensivo_PFF**: Jugada en la que algún jugador tiene `pff_hit`, `pff_hurry` o `pff_sack` igual a 1 (`hasPffPressure`).
- **Cargo_Ofensivo**: Jugada en la que algún Bloqueador tiene `pff_hitAllowed`, `pff_hurryAllowed` o `pff_sackAllowed` igual a 1 (`hasOffensiveCharge`).
- **Cuadro_Snap**: Cuadro de tracking del snap, elegido según el Requisito 7.
- **Cuadro_Pase**: Cuadro de tracking del lanzamiento, elegido según el Requisito 7.
- **Cuadro_Amenaza**: Primer cuadro posterior al Cuadro_Snap en que algún Rusher está a 2.0 yardas o menos del QB.
- **timeToThrow**: `(Cuadro_Pase - Cuadro_Snap) / 10`, en segundos.
- **threatTime**: `(Cuadro_Amenaza - Cuadro_Snap) / 10`, en segundos; etiquetado como "tiempo hasta amenaza por proximidad".
- **Coordenadas_Normalizadas**: `x_norm` y `y_norm` según el Requisito 8.
- **Sector**: Una de cinco clases geométricas de PocketIQ (Izquierda, Interior izquierda, Centro, Interior derecha, Derecha) definidas en el Requisito 11.
- **Diagnostico**: Etiqueta de `pressureSourceCandidate` definida en el Requisito 12. Una jugada puede tener varias.
- **Calidad_Muestra**: Clasificación del tamaño de muestra n: amplia (n >= 100), moderada (30 <= n < 100), pequeña (10 <= n < 30), insuficiente (n < 10).
- **Fuente_Etiqueta**: Clasificación de cada dato mostrado: "observada", "PFF" o "inferida".
- **Banda_Distancia**: Clasificación de `yardsToGo` definida en el Requisito 6.
- **Zona_Campo**: Clasificación de la posición del balón definida en el Requisito 5.

## Requirements

### Requisito 1: Estructura, despliegue y rutas

**User Story:** Como equipo de desarrollo, quiero que PocketIQ respete el contrato de despliegue del hackathon, para que AWS pueda hospedar la aplicación sin cambios.

#### Acceptance Criteria

1. THE Backend SHALL exponer el objeto `app = FastAPI(...)` en `backend/main.py`.
2. WHEN se recibe `GET /health`, THE Backend SHALL responder con código 200 y el cuerpo JSON `{"status": "ok"}`.
3. THE Backend SHALL publicar todos los endpoints de datos bajo el prefijo `/api/`.
4. THE Backend SHALL servir los archivos de `dashboard/dist` y la API desde la misma URL y el mismo puerto.
5. THE Dashboard SHALL invocar la API con rutas relativas sin diagonal inicial, con la forma `api/<ruta>`.
6. THE Dashboard SHALL referenciar imágenes, estilos y enlaces con rutas relativas sin diagonal inicial, sin `localhost`, sin `127.0.0.1` y sin URLs absolutas.
7. THE Dashboard SHALL conservar `base: './'` en `dashboard/vite.config.ts` y definir un proxy de `/api` hacia `http://localhost:8000` para desarrollo.
8. WHEN se ejecuta `npm run build` en `dashboard/`, THE Dashboard SHALL generar el build en `dashboard/dist` sin errores de TypeScript.
9. THE PocketIQ SHALL usar únicamente las dependencias y versiones listadas en `.kiro/steering/rules.md`.
10. THE Motor_Analitico SHALL residir en `backend/analytics.py` y THE Esquemas SHALL residir en `backend/schemas.py`.

### Requisito 2: Carga de datos y manejo de memoria

**User Story:** Como entrenador ofensivo, quiero que la aplicación responda con datos reales sin agotar la memoria del servidor, para que pueda consultar cualquier rival de forma estable.

#### Acceptance Criteria

1. THE Motor_Analitico SHALL leer únicamente `data/games.csv`, `data/plays.csv`, `data/players.csv`, `data/pffScoutingData.csv` y `data/tracking/tracking_<gameId>.csv`, con rutas relativas a la raíz del proyecto.
2. THE Motor_Analitico SHALL abrir los archivos de `data/` solo en modo lectura, sin crear, modificar ni borrar archivos dentro de `data/`.
3. WHEN el Backend arranca, THE Motor_Analitico SHALL cargar `games.csv`, `plays.csv`, `players.csv` y `pffScoutingData.csv` en memoria una sola vez y calcular los agregados de PFF por jugada.
4. WHEN se solicita un análisis de un Rival cuyos agregados de tracking no están en Cache_Tracking, THE Motor_Analitico SHALL leer solo los archivos de tracking de los partidos en que jugó ese Rival, un archivo a la vez.
5. WHEN el Motor_Analitico lee un archivo de tracking, THE Motor_Analitico SHALL leer solo las columnas `gameId`, `playId`, `nflId`, `frameId`, `team`, `playDirection`, `x`, `y` y `event`.
6. WHEN el Motor_Analitico termina de procesar un archivo de tracking, THE Motor_Analitico SHALL conservar solo los agregados por jugada y las trayectorias necesarias, y liberar el DataFrame del archivo.
7. THE Cache_Tracking SHALL almacenar los agregados de tracking por Rival y los resultados de análisis por combinación de filtros, solo en memoria.
8. WHILE una solicitud está calculando los agregados de un Rival, THE Cache_Tracking SHALL impedir que otra solicitud concurrente calcule o escriba los agregados del mismo Rival.
9. THE Motor_Analitico SHALL funcionar sin depender de archivos calculados previamente en disco.
10. THE Motor_Analitico SHALL unir games con plays por `gameId`, plays con PFF por `gameId` y `playId`, PFF con players por `nflId`, plays con tracking por `gameId` y `playId`, y PFF con tracking por `gameId`, `playId` y `nflId`.
11. THE Motor_Analitico SHALL identificar jugadores únicamente por `nflId`, sin unir por `displayName`.

### Requisito 3: Validaciones de integridad de datos

**User Story:** Como analista, quiero que la aplicación compruebe la integridad de los datos, para que pueda confiar en que las métricas no provienen de uniones o cálculos erróneos.

#### Acceptance Criteria

1. WHEN el Motor_Analitico carga `plays.csv`, THE Validador_Datos SHALL comprobar que la llave (`gameId`, `playId`) es única.
2. WHEN el Motor_Analitico carga `pffScoutingData.csv`, THE Validador_Datos SHALL comprobar que cada `nflId` existe en `players.csv`.
3. WHEN el Motor_Analitico carga `pffScoutingData.csv`, THE Validador_Datos SHALL comprobar que cada jugada tiene 11 jugadores ofensivos y 11 defensivos.
4. WHEN el Motor_Analitico procesa un archivo de tracking, THE Validador_Datos SHALL comprobar que cada valor de `team` coincide con `possessionTeam`, `defensiveTeam` o `"football"` de la jugada.
5. WHEN el Motor_Analitico procesa un archivo de tracking, THE Validador_Datos SHALL comprobar que cada cuadro de cada jugada tiene exactamente una fila del balón.
6. WHEN el Motor_Analitico calcula timeToThrow o threatTime, THE Validador_Datos SHALL comprobar que el valor es mayor o igual a cero y que el Cuadro_Pase es posterior al Cuadro_Snap.
7. IF una comprobación del Validador_Datos falla, THEN THE Motor_Analitico SHALL registrar una advertencia técnica con el nombre de la comprobación y el número de casos afectados, y continuar el procesamiento excluyendo solo el valor inválido.
8. THE Motor_Analitico SHALL limitar cada advertencia técnica a un resumen por comprobación y por archivo, sin registrar filas individuales ni credenciales.
9. THE Motor_Analitico SHALL producir tasas con valores entre 0 y 1 y conteos con valores mayores o iguales a 0.

### Requisito 4: Tabla analítica por jugada

**User Story:** Como entrenador ofensivo, quiero que cada jugada quede resumida en una fila con contexto, protección y presión, para que los filtros y comparaciones operen sobre una unidad consistente.

#### Acceptance Criteria

1. THE Motor_Analitico SHALL construir la Tabla_Analitica con una fila por jugada y las columnas `gameId`, `playId`, `week`, `possessionTeam`, `defensiveTeam`, `quarter`, `gameClock`, `down`, `yardsToGo`, `distanceBand`, `fieldZone`, `offenseFormation`, `personnelO`, `personnelD`, `defendersInBox`, `playAction`, `dropBackType`, `coverage`, `coverageType`, `passResult`, `prePenaltyPlayResult`, `playResult`, `passRushers`, `passBlockers`, `hasPffPressure`, `hasHurry`, `hasHit`, `hasSack`, `hasBeatenBlocker`, `hasOffensiveCharge`, `timeToThrow`, `threatTime`, `threatSide`, `pressureSourceCandidate` y `sampleQuality`.
2. THE Motor_Analitico SHALL calcular `passRushers` como el número de jugadores de la jugada con `pff_role == "Pass Rush"`.
3. THE Motor_Analitico SHALL calcular `passBlockers` como el número de jugadores de la jugada con `pff_role == "Pass Block"`.
4. THE Motor_Analitico SHALL identificar como Ayuda_Chip a cada jugador con `pff_role == "Pass Route"` y `pff_blockType` o `pff_nflIdBlockedPlayer` no nulo, sin sumarlo a `passBlockers`.
5. THE Motor_Analitico SHALL marcar una jugada como Blitz_Aproximado cuando `passRushers >= 5`.
6. THE Dashboard SHALL mostrar el Blitz_Aproximado con la etiqueta "blitz aproximado".
7. THE Motor_Analitico SHALL calcular `hasPffPressure` como verdadero cuando el máximo de `pff_hit`, `pff_hurry` y `pff_sack` entre los jugadores de la jugada es 1.
8. THE Motor_Analitico SHALL calcular `hasHurry`, `hasHit`, `hasSack`, `hasBeatenBlocker` y `hasOffensiveCharge` como columnas separadas.
9. THE Motor_Analitico SHALL calcular `hasOffensiveCharge` solo a partir de `pff_hitAllowed`, `pff_hurryAllowed` y `pff_sackAllowed`, separado de las marcas defensivas `pff_hit`, `pff_hurry` y `pff_sack`.
10. THE Motor_Analitico SHALL calcular la tasa de sack por `passResult == "S"` y, por separado, la tasa de `pff_sack`, sin reemplazar una por la otra.
11. WHEN la tasa de sack por `passResult` y la tasa por `pff_sack` difieren en la muestra, THE API SHALL incluir ambas tasas y el número de jugadas en que difieren.
12. THE Dashboard SHALL describir `hasPffPressure` como "Evento defensivo PFF (hit, hurry o sack)", una definición operativa de PocketIQ.
13. IF un campo de origen es nulo, THEN THE Motor_Analitico SHALL guardar el valor derivado como nulo, sin sustituirlo por cero.

### Requisito 5: Zona del campo

**User Story:** Como entrenador ofensivo, quiero filtrar por la zona del campo, para que pueda estudiar cómo cambia la presión cerca de la zona roja o en campo propio.

#### Acceptance Criteria

1. WHEN `yardlineNumber == 50`, THE Motor_Analitico SHALL asignar una distancia a la zona de anotación de 50.
2. WHEN `yardlineNumber != 50` y `yardlineSide == possessionTeam`, THE Motor_Analitico SHALL asignar una distancia a la zona de anotación de `100 - yardlineNumber`.
3. WHEN `yardlineNumber != 50` y `yardlineSide != possessionTeam`, THE Motor_Analitico SHALL asignar una distancia a la zona de anotación igual a `yardlineNumber`.
4. WHEN `down == 0`, THE Motor_Analitico SHALL asignar la Zona_Campo "Conversión de dos puntos".
5. WHEN `down != 0`, THE Motor_Analitico SHALL asignar la Zona_Campo "Propio 1–20" a distancias de 80 a 99, "Propio 21–40" a distancias de 60 a 79, "Medio campo" a distancias de 40 a 59, "Territorio rival" a distancias de 21 a 39 y "Zona roja" a distancias de 20 o menos.
6. IF `yardlineSide` es nulo y `yardlineNumber != 50`, THEN THE Motor_Analitico SHALL asignar `fieldZone` nulo y registrar el caso en las advertencias técnicas.

### Requisito 6: Banda de distancia

**User Story:** Como entrenador ofensivo, quiero agrupar las situaciones por distancia por avanzar, para que obtenga muestras comparables sin fragmentar los datos por yarda exacta.

#### Acceptance Criteria

1. WHEN `down == 0`, THE Motor_Analitico SHALL asignar la Banda_Distancia "Conversión".
2. WHEN `down != 0`, THE Motor_Analitico SHALL asignar la Banda_Distancia "Corta" a `yardsToGo` de 1 a 3, "Media" de 4 a 6, "Larga" de 7 a 10 y "Muy larga" de 11 o más.
3. WHERE el usuario indica una distancia exacta, THE Motor_Analitico SHALL filtrar por `yardsToGo` igual a ese valor.
4. THE Dashboard SHALL mostrar la Banda_Distancia como opción recomendada frente a la distancia exacta.

### Requisito 7: Eventos de snap y pase y tiempo de lanzamiento

**User Story:** Como entrenador ofensivo, quiero saber cuánto tarda el QB en lanzar, para que pueda relacionar el ritmo de la jugada con la presión.

#### Acceptance Criteria

1. THE Motor_Analitico SHALL elegir el Cuadro_Snap a partir del evento `ball_snap` y, solo cuando la jugada no tiene `ball_snap`, a partir de `autoevent_ballsnap`.
2. THE Motor_Analitico SHALL elegir el Cuadro_Pase a partir del evento `pass_forward` y, solo cuando la jugada no tiene `pass_forward`, a partir de `autoevent_passforward`.
3. WHEN una jugada tiene varios cuadros con el evento elegido, THE Motor_Analitico SHALL tomar el cuadro de menor `frameId` de ese evento.
4. THE Motor_Analitico SHALL tratar la cadena literal `"None"` en `event` como ausencia de evento.
5. THE Motor_Analitico SHALL calcular timeToThrow como `(Cuadro_Pase - Cuadro_Snap) / 10`, a partir de `frameId` y sin usar la columna `time`.
6. IF una jugada no tiene Cuadro_Snap o no tiene Cuadro_Pase, THEN THE Motor_Analitico SHALL asignar timeToThrow nulo y registrar el motivo ("sin snap" o "sin pase").
7. THE Motor_Analitico SHALL registrar para cada jugada si cada evento provino de la marca manual o de la marca automática.

### Requisito 8: Normalización de coordenadas

**User Story:** Como analista, quiero que todas las jugadas se vean en la misma dirección de ataque, para que las comparaciones espaciales entre jugadas sean válidas.

#### Acceptance Criteria

1. WHEN `playDirection == "right"`, THE Motor_Analitico SHALL calcular `x_norm = x` y `y_norm = y`.
2. WHEN `playDirection == "left"`, THE Motor_Analitico SHALL calcular `x_norm = 120 - x` y `y_norm = 53.3 - y`.
3. THE Motor_Analitico SHALL conservar `x` e `y` originales junto a las Coordenadas_Normalizadas para depuración.
4. FOR ALL coordenadas de tracking, aplicar la normalización dos veces a una jugada con `playDirection == "left"` SHALL devolver las coordenadas originales (propiedad de involución).

### Requisito 9: Tiempo hasta amenaza por proximidad

**User Story:** Como entrenador ofensivo, quiero saber cuánto tarda un rusher en llegar cerca del QB, para que pueda estimar el margen que tiene mi protección.

#### Acceptance Criteria

1. THE Motor_Analitico SHALL calcular, para cada Rusher y cada cuadro posterior al Cuadro_Snap, la distancia euclidiana en Coordenadas_Normalizadas entre el Rusher y el QB.
2. WHEN algún Rusher está a 2.0 yardas o menos del QB en un cuadro posterior al Cuadro_Snap, THE Motor_Analitico SHALL asignar el primero de esos cuadros como Cuadro_Amenaza y calcular threatTime como `(Cuadro_Amenaza - Cuadro_Snap) / 10`.
3. IF ningún Rusher llega a 2.0 yardas o menos del QB, THEN THE Motor_Analitico SHALL asignar threatTime nulo y conservar la distancia mínima alcanzada y el tiempo desde el snap en que ocurrió.
4. IF ningún Rusher llega a 2.0 yardas o menos del QB, THEN THE Motor_Analitico SHALL omitir la clasificación de presión basada en la distancia mínima.
5. THE Dashboard SHALL mostrar threatTime con la etiqueta "tiempo hasta amenaza por proximidad" y Fuente_Etiqueta "inferida".
6. IF la jugada no tiene Cuadro_Snap o no tiene QB identificado, THEN THE Motor_Analitico SHALL asignar threatTime nulo y registrar el motivo.
7. THE Motor_Analitico SHALL evaluar la proximidad desde el Cuadro_Snap hasta el Cuadro_Pase, el cuadro de sack o el último cuadro de la jugada, el que ocurra primero.

### Requisito 10: Calidad de muestra

**User Story:** Como entrenador ofensivo, quiero ver siempre cuántas jugadas sustentan cada resultado, para que no tome decisiones con muestras pequeñas.

#### Acceptance Criteria

1. THE API SHALL incluir el número de jugadas n y el número de partidos en cada respuesta de análisis.
2. THE Motor_Analitico SHALL asignar la Calidad_Muestra "amplia" cuando n >= 100, "moderada" cuando 30 <= n < 100, "pequeña" cuando 10 <= n < 30 e "insuficiente" cuando n < 10.
3. THE Dashboard SHALL mostrar n y la Calidad_Muestra en el resumen ejecutivo y junto a cada tabla y gráfica.
4. WHEN n < 30, THE Dashboard SHALL mostrar una advertencia visible con borde y texto, además del color.
5. WHEN n < 30, THE Generador_Resumen SHALL omitir frases de recomendación categórica.
6. WHEN n < 30, THE Dashboard SHALL mostrar un botón para ampliar filtros que sugiera quitar primero, en este orden, semana, cobertura y distancia exacta.
7. IF n == 0, THEN THE API SHALL devolver métricas nulas, listas vacías y la lista de filtros activos que dejaron la consulta vacía, sin calcular divisiones entre cero.
8. IF n == 0, THEN THE Dashboard SHALL mostrar un estado vacío que explique qué filtros dejaron la consulta sin jugadas.

### Requisito 11: Lado de entrada de la amenaza

**User Story:** Como entrenador ofensivo, quiero saber por qué lado entra la amenaza, para que pueda ajustar la protección hacia ese lado.

#### Acceptance Criteria

1. WHEN una jugada tiene Cuadro_Amenaza, THE Motor_Analitico SHALL calcular `lateralDelta = rusher_y_norm - qb_y_norm` para el Rusher que activó la amenaza en ese cuadro.
2. THE Motor_Analitico SHALL asignar el Sector "Izquierda" cuando `lateralDelta >= 4.0`, "Interior izquierda" cuando `1.5 <= lateralDelta < 4.0`, "Centro" cuando `-1.5 < lateralDelta < 1.5`, "Interior derecha" cuando `-4.0 < lateralDelta <= -1.5` y "Derecha" cuando `lateralDelta <= -4.0`.
3. IF una jugada no tiene Cuadro_Amenaza, THEN THE Motor_Analitico SHALL asignar `threatSide` nulo.
4. THE Suite_Pruebas SHALL validar la orientación de los Sectores contra jugadas conocidas antes de que el Dashboard muestre las etiquetas de Sector.
5. IF la validación de orientación muestra Sectores invertidos, THEN THE Motor_Analitico SHALL corregir una sola vez la transformación global de coordenadas, sin ajustes por jugada.
6. THE Dashboard SHALL indicar que los Sectores son una clasificación geométrica de PocketIQ y no una etiqueta oficial de PFF.
7. FOR ALL valores reales de `lateralDelta`, THE Motor_Analitico SHALL asignar exactamente un Sector (propiedad de partición).

### Requisito 12: Diagnóstico de protección

**User Story:** Como entrenador ofensivo, quiero ver posibles fuentes de presión por jugada, para que pueda orientar la revisión en video hacia los problemas más frecuentes.

#### Acceptance Criteria

1. THE Motor_Analitico SHALL asignar a cada jugada una o más etiquetas de Diagnostico en `pressureSourceCandidate`.
2. WHEN algún Bloqueador de la jugada tiene `pff_beatenByDefender`, `pff_hitAllowed`, `pff_hurryAllowed` o `pff_sackAllowed` igual a 1, THE Motor_Analitico SHALL asignar el Diagnostico "Derrota individual" con Fuente_Etiqueta "PFF".
3. WHEN un Rusher tiene un `nflId` ausente de todos los `pff_nflIdBlockedPlayer` de la jugada y llega a 2.0 yardas o menos del QB, THE Motor_Analitico SHALL asignar el Diagnostico "Posible rusher libre" con Fuente_Etiqueta "inferida".
4. WHEN dos o más Bloqueadores de la jugada comparten el mismo `pff_nflIdBlockedPlayer`, THE Motor_Analitico SHALL asignar el Diagnostico "Doble equipo" con Fuente_Etiqueta "PFF".
5. THE Dashboard SHALL indicar que el Diagnostico "Doble equipo" no implica que el doble equipo se mantuvo toda la jugada.
6. WHEN algún jugador tiene `pff_blockType == "CH"` o la jugada tiene al menos una Ayuda_Chip, THE Motor_Analitico SHALL asignar el Diagnostico "Chip o ayuda" con Fuente_Etiqueta "PFF".
7. WHEN el Bloqueador más cercano a un Rusher cambia entre dos Bloqueadores de posiciones adyacentes (LT-LG, LG-C, C-RG, RG-RT), el Rusher cruza lateralmente la trayectoria de otro Rusher y el patrón se sostiene durante al menos el número de cuadros consecutivos definido en el diseño, THE Motor_Analitico SHALL asignar el Diagnostico "Posible intercambio o stunt" con Fuente_Etiqueta "inferida".
8. WHEN timeToThrow es mayor que el umbral contextual de jugadas comparables, la jugada no tiene "Derrota individual" antes de ese umbral, el Cuadro_Amenaza ocurre después del umbral y el QB se desplaza hacia el Rusher o sale de la bolsa, THE Motor_Analitico SHALL asignar el Diagnostico "Posible presión prolongada por movimiento o retención del QB" con Fuente_Etiqueta "inferida".
9. WHEN ninguna regla de los criterios 2 a 8 encuentra evidencia en la jugada, THE Motor_Analitico SHALL asignar el Diagnostico "No determinado con los datos disponibles".
10. THE Dashboard SHALL mostrar cada Diagnostico inferido con la palabra "Posible" o "heurística" y con su Fuente_Etiqueta.
11. THE Dashboard SHALL mostrar los Diagnosticos sin atribuir responsabilidad definitiva a un jugador.

### Requisito 13: Filtros

**User Story:** Como entrenador ofensivo, quiero combinar filtros de situación, para que pueda reproducir la situación que espero enfrentar contra el rival.

#### Acceptance Criteria

1. WHEN se recibe `GET /api/filters`, THE API SHALL responder con las listas `opponents`, `downs`, `distanceBands`, `offenseFormations`, `defensivePersonnels`, `blockerCounts`, `fieldZones`, `dropBackTypes`, `coverages` y `weeks`, con valores obtenidos del dataset.
2. THE Dashboard SHALL ofrecer filtros de Rival, down, Banda_Distancia, distancia exacta opcional, formación ofensiva, personal defensivo, play action (Todos, Sí, No), número de Bloqueadores, Zona_Campo, tipo de dropback, cobertura ejecutada opcional y semana opcional.
3. THE Dashboard SHALL incluir la opción "Todos" en cada filtro.
4. THE Dashboard SHALL ubicar el filtro de cobertura ejecutada en una sección de análisis posterior, con la nota de que la cobertura no se conoce antes del snap.
5. WHILE el Dashboard se muestra en escritorio, THE Dashboard SHALL presentar los filtros en una columna lateral.
6. WHILE el Dashboard se muestra en un ancho de pantalla móvil, THE Dashboard SHALL presentar los filtros en un panel desplegable.
7. WHEN el usuario pulsa "Analizar defensa", THE Dashboard SHALL enviar `POST api/analysis` con los filtros seleccionados.
8. IF un filtro recibe una categoría que no existe en el dataset, THEN THE API SHALL devolver una respuesta válida con n == 0 o un error 422 descriptivo, sin error 500.

### Requisito 14: Endpoint de análisis

**User Story:** Como entrenador ofensivo, quiero obtener en una sola consulta el resumen, el mapa de presión y las comparaciones, para que el dashboard se actualice de forma coherente.

#### Acceptance Criteria

1. WHEN se recibe `POST /api/analysis` con los campos `opponent`, `down`, `distanceBand`, `exactDistance`, `offenseFormation`, `defensivePersonnel`, `playAction`, `passBlockers`, `fieldZone`, `dropBackType`, `coverage` y `week`, THE API SHALL validar la entrada con los Esquemas.
2. WHEN la entrada es válida, THE API SHALL responder con `filtersApplied`, `sample` (`plays`, `games`, `quality`, `warning`), `summary` (`text`, `blitzRate`, `averageRushers`, `pffPressureRate`, `hurryRate`, `hitRate`, `sackRate`, `averageThreatTime`, `averageTimeToThrow`), `pressureMap`, `diagnoses`, `rusherDistribution`, `coverageDistribution`, `protectionResponses` y `representativePlays`.
3. THE API SHALL incluir en `pressureMap` los cinco Sectores, cada uno con `sector`, `plays`, `share`, `averageThreatTime`, `hurries`, `hits` y `sacks`, incluso cuando un Sector tiene 0 jugadas.
4. THE API SHALL serializar los valores faltantes como `null`, sin `NaN` ni infinitos en el JSON.
5. IF la entrada no cumple los Esquemas, THEN THE API SHALL responder con código 422 y un mensaje que identifique el campo inválido.
6. WHEN una combinación de filtros ya se calculó, THE Motor_Analitico SHALL devolver el resultado desde Cache_Tracking.
7. WHILE el primer análisis de un Rival está en proceso, THE Dashboard SHALL mostrar un mensaje de estado de carga.

### Requisito 15: Detalle de jugada

**User Story:** Como entrenador ofensivo, quiero abrir una jugada y ver su tracking, para que pueda verificar visualmente el diagnóstico antes de revisarla en video.

#### Acceptance Criteria

1. WHEN se recibe `GET /api/plays/{game_id}/{play_id}` de una jugada existente, THE API SHALL responder con el contexto de la jugada, `playDescription`, los jugadores con `nflId`, nombre, posición y `pff_role`, los Diagnosticos, los eventos disponibles y las trayectorias en Coordenadas_Normalizadas.
2. THE API SHALL limitar las trayectorias del detalle a los cuadros desde el Cuadro_Snap hasta el Cuadro_Pase, el cuadro de sack o el último cuadro, el que ocurra primero.
3. THE API SHALL incluir la Fuente_Etiqueta ("PFF", "observada" o "inferida") de cada etiqueta del detalle.
4. IF la jugada solicitada no existe, THEN THE API SHALL responder con código 404 y un mensaje descriptivo.
5. IF la jugada no tiene Cuadro_Snap, THEN THE API SHALL responder con el contexto disponible, trayectorias vacías y el motivo.

### Requisito 16: Resumen automático

**User Story:** Como entrenador ofensivo, quiero un resumen en lenguaje claro, para que pueda leer el hallazgo principal sin interpretar todas las gráficas.

#### Acceptance Criteria

1. THE Generador_Resumen SHALL producir el texto del resumen con una plantilla determinista a partir de n, el Rival, la tasa de Blitz_Aproximado, el Sector más frecuente, el threatTime promedio, el Diagnostico más frecuente y la Calidad_Muestra.
2. THE Generador_Resumen SHALL producir el mismo texto para la misma entrada de filtros y los mismos datos.
3. THE Generador_Resumen SHALL usar expresiones de asociación como "se asocia con", "presentó menor tasa observada", "posible fuente", "en esta muestra" y "requiere validación en video".
4. THE Generador_Resumen SHALL redactar sin frases causales como "esta formación evita la presión", "el tackle causó el sack" o "esta es la mejor jugada".
5. THE Generador_Resumen SHALL generar el texto sin servicios de IA generativa.
6. WHEN n < 30, THE Generador_Resumen SHALL incluir una frase que indique que la muestra es pequeña y debe interpretarse con cautela.

### Requisito 17: Panel de resumen, tarjetas y mapa de presión

**User Story:** Como entrenador ofensivo, quiero ver de un vistazo las métricas clave y el mapa de presión, para que identifique rápido el patrón de ataque del rival.

#### Acceptance Criteria

1. THE Dashboard SHALL mostrar un encabezado con "PocketIQ", "¿Cómo nos va a atacar esta defensa?" y "Herramienta de preparación ofensiva basada en tendencias históricas de presión, protección y tracking."
2. THE Dashboard SHALL mostrar el resumen ejecutivo con el texto de la API, n y la Calidad_Muestra.
3. THE Dashboard SHALL mostrar tarjetas de Blitz aproximado, Rushers promedio, Evento defensivo PFF, Tiempo promedio hasta amenaza, Hurry rate, Hit rate, Sack rate y Tiempo promedio de lanzamiento, cada una con su Fuente_Etiqueta.
4. THE Mapa_Presion SHALL dibujar en SVG, sin dependencias adicionales, los Sectores Izquierda, Interior izquierda, Centro, Interior derecha y Derecha.
5. THE Mapa_Presion SHALL mostrar en cada Sector la participación, el threatTime promedio, hurries, hits, sacks y n, con texto numérico además de la intensidad de color.
6. THE Mapa_Presion SHALL mostrar la leyenda "Los sectores representan la posición del rusher respecto del QB en el primer cuadro de amenaza por proximidad."

### Requisito 18: Tendencias defensivas y diagnóstico en el dashboard

**User Story:** Como entrenador ofensivo, quiero ver la distribución de rushers, coberturas y diagnósticos, para que entienda el repertorio del rival.

#### Acceptance Criteria

1. THE Dashboard SHALL mostrar con Recharts la distribución de rushers, la frecuencia de Blitz_Aproximado, las coberturas ejecutadas, el personal defensivo y la presión por down y Banda_Distancia.
2. THE Dashboard SHALL mostrar el diagnóstico de protección como tabla o barras con las siete categorías de Diagnostico y, por categoría, jugadas, porcentaje, hurries, hits, sacks y threatTime promedio.
3. THE Dashboard SHALL mostrar las coberturas como "cobertura ejecutada (PFF)".

### Requisito 19: Respuesta ofensiva

**User Story:** Como entrenador ofensivo, quiero comparar alternativas de protección contra este rival, para que elija qué opciones revisar en video.

#### Acceptance Criteria

1. THE API SHALL incluir en `protectionResponses` comparaciones por formación ofensiva, número de Bloqueadores, play action frente a convencional, rollout izquierdo frente a derecho (`dropBackType`), tipo de bloqueo y personal ofensivo.
2. THE API SHALL incluir por alternativa n, tasa de Evento_Defensivo_PFF, tasa de sack, threatTime promedio, tasa de pases completos, yardas promedio antes de penalización (`prePenaltyPlayResult`), yardas promedio finales (`playResult`) y Calidad_Muestra.
3. THE Dashboard SHALL ordenar inicialmente las alternativas de menor a mayor tasa de Evento_Defensivo_PFF.
4. WHEN el usuario pulsa el encabezado de una columna, THE Dashboard SHALL ordenar la tabla por esa columna.
5. WHEN una alternativa tiene n < 30, THE Dashboard SHALL mostrar la alternativa sin la palabra "recomendación" y con la advertencia de muestra pequeña.

### Requisito 20: Jugadas representativas

**User Story:** Como entrenador ofensivo, quiero ejemplos concretos del patrón, para que pueda ir directo a las jugadas que vale la pena revisar.

#### Acceptance Criteria

1. THE API SHALL incluir en `representativePlays`, cuando existan en la muestra, una jugada típica, una de amenaza temprana, una con sack, una con protección exitosa comparable y una con "Posible intercambio o stunt" o "Posible rusher libre".
2. THE Motor_Analitico SHALL elegir cada jugada representativa con una regla determinista documentada en el diseño.
3. THE Dashboard SHALL mostrar por jugada representativa partido y semana, down y distancia, formación, personal defensivo, rushers y Bloqueadores, cobertura, timeToThrow, threatTime, resultado, descripción, Diagnosticos y nivel de confianza.
4. WHEN el usuario selecciona una jugada representativa, THE Dashboard SHALL abrir el detalle de tracking de esa jugada con `api/plays/{game_id}/{play_id}`.
5. IF una categoría de jugada representativa no tiene ejemplos en la muestra, THEN THE Dashboard SHALL indicar que no hay ejemplos de esa categoría.

### Requisito 21: Diseño visual y accesibilidad

**User Story:** Como entrenador ofensivo, quiero una interfaz legible tipo sala de análisis, para que pueda usarla en una reunión de preparación en pantalla grande o en móvil.

#### Acceptance Criteria

1. THE Dashboard SHALL usar fondo oscuro, verde campo como color secundario, rojo o naranja para amenazas y azul para protección, con Tailwind CSS 3.
2. THE Dashboard SHALL acompañar cada indicador de color con una etiqueta de texto, un porcentaje, un icono de texto o CSS, un patrón o un borde.
3. THE Dashboard SHALL adaptar el diseño a anchos de escritorio y móvil.
4. THE Dashboard SHALL usar solo recursos locales, sin imágenes externas ni rutas absolutas.

### Requisito 22: Pruebas automatizadas

**User Story:** Como equipo de desarrollo, quiero pruebas que cubran las reglas analíticas, para que los cambios no rompan las definiciones.

#### Acceptance Criteria

1. THE Suite_Pruebas SHALL probar `GET /health`, `GET /api/filters`, `POST /api/analysis` con una consulta válida y con una consulta sin resultados.
2. THE Suite_Pruebas SHALL probar la Banda_Distancia, la Zona_Campo, la normalización izquierda y derecha, la prioridad de eventos manuales, timeToThrow, Blitz_Aproximado, "Doble equipo", "Posible rusher libre", el manejo de faltantes y la Calidad_Muestra.
3. THE Suite_Pruebas SHALL comprobar que las respuestas JSON de la API no contienen `NaN` ni infinitos.
4. THE Suite_Pruebas SHALL usar muestras pequeñas construidas en memoria para las pruebas unitarias, sin cargar todos los archivos de tracking.
5. FOR ALL valores de `yardsToGo` de 1 a 99 con `down` de 1 a 4, THE Motor_Analitico SHALL asignar exactamente una Banda_Distancia (propiedad de partición).
6. FOR ALL distancias a la zona de anotación de 1 a 99 con `down` de 1 a 4, THE Motor_Analitico SHALL asignar exactamente una Zona_Campo (propiedad de partición).
7. FOR ALL conjuntos de filtros, THE Motor_Analitico SHALL devolver tasas entre 0 y 1 y conteos mayores o iguales a 0 (invariante).
8. FOR ALL conjuntos de filtros, agregar un filtro adicional SHALL producir un n menor o igual al n sin ese filtro (propiedad metamórfica).

### Requisito 23: Criterios de cierre

**User Story:** Como equipo de desarrollo, quiero criterios claros de terminado, para que sepamos cuándo detener la implementación.

#### Acceptance Criteria

1. WHEN se ejecuta `sh .hackathon/setup.sh --check`, THE PocketIQ SHALL pasar la verificación del entorno.
2. WHEN se ejecuta la Suite_Pruebas con pytest, THE Suite_Pruebas SHALL terminar sin fallas.
3. WHEN se ejecuta `npm run build` en `dashboard/`, THE Dashboard SHALL compilar sin errores.
4. WHEN termina la implementación, THE PocketIQ SHALL dejar sin cambios todos los archivos de `data/`.
5. THE Dashboard SHALL mostrar resultados calculados del dataset real para cualquier Rival seleccionado.
