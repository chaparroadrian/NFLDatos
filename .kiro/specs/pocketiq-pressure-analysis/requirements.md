# Requirements Document

## Introduction

PocketIQ ("¿Cómo nos va a atacar esta defensa?") es una aplicación web para que un entrenador ofensivo estudie las tendencias de presión de un rival defensivo, entienda por dónde y cuándo entra la presión y compare las respuestas de protección observadas. La aplicación usa los datos del NFL Big Data Bowl (temporada 2021, semanas 1 a 8): contexto de jugada, etiquetas de PFF y tracking cuadro por cuadro.

La aplicación debe responder preguntas como: "En tercera y larga, con cinco bloqueadores y formación shotgun, ¿con qué frecuencia manda cinco o más rushers esta defensa, por dónde entra la amenaza, cuánto tarda en aparecer y qué protecciones se asocian con mejores resultados?".

Toda métrica mostrada se clasifica en una de cuatro fuentes: variable observada, etiqueta PFF, inferencia heurística o resultado con muestra insuficiente. Ninguna inferencia se presenta como asignación confirmada por el equipo o por video.

El stack, la estructura de carpetas y el contrato de despliegue siguen `.kiro/steering/rules.md`: FastAPI en `backend/`, React + Vite + Tailwind 3 + Recharts en `dashboard/`, sin dependencias nuevas, datos de solo lectura y servidor efímero. Como función opcional, PocketIQ usa modelos Amazon Nova mediante Amazon Bedrock (strands-agents 1.64.0 y boto3 1.44.0, ya incluidos en el stack) para tres asistentes: Analista de tendencias, Asistente de diagnóstico y Generador de scouting report (Requisitos 24 a 28). Python calcula todas las estadísticas; Nova solo redacta explicaciones a partir de esos valores. La aplicación funciona y muestra su hallazgo principal aunque la IA no esté disponible.

### Supuestos

1. **Rutas de datos.** Las instrucciones originales mencionan `data/nfl-big-data-bowl-regional-event-data-main/data/...`. En el espacio de trabajo los archivos están en `data/games.csv`, `data/plays.csv`, `data/players.csv`, `data/pffScoutingData.csv` y `data/tracking/tracking_<gameId>.csv` (122 archivos, 8,314,178 filas). Se usan estas rutas reales, relativas a la raíz del proyecto.
2. **Documento de verificación.** Las instrucciones mencionan `verificacion_datos.md`, que no existe. La fuente de hechos verificados es `diagnostico_inicial.md`, complementada con estos hechos aportados durante la preparación: todas las jugadas son dropbacks de pase; cada jugada tiene 22 jugadores en PFF; cada cuadro de tracking tiene 23 filas (22 jugadores y el balón); el tracking se muestrea a 10 cuadros por segundo; la columna `event` usa la cadena literal `"None"` en cuadros sin evento; 24 jugadas no tienen evento de snap; 3,746 jugadas tienen más de un cuadro marcado como snap; los valores de `pff_role` vienen capitalizados (`"Pass Block"`, `"Pass Route"`, `"Pass Rush"`, `"Pass"`, `"Coverage"`); 35 jugadas tienen `down == 0` (conversiones de dos puntos); `yardlineSide` es nulo cuando `yardlineNumber == 50`.
3. **Código existente.** `backend/main.py` contiene solo `GET /health`. `dashboard/` contiene un andamiaje de Vite + React (`src/App.tsx`, `src/main.tsx`, `src/index.css`) y `vite.config.ts` con `base: './'` y sin proxy. La implementación extiende estos archivos y crea `backend/analytics.py` y `backend/schemas.py`.
4. **Varios cuadros de snap.** Cuando una jugada tiene más de un cuadro con el evento de snap elegido, se toma el primer cuadro (menor `frameId`) de ese evento. Este criterio es un supuesto del documento y se puede revisar en el diseño.
5. **Umbrales contextuales.** Los umbrales "timeToThrow alto respecto de comparables" y "amenaza tras umbral contextual" (Requisito 12) se fijarán en el diseño a partir de percentiles de la muestra filtrada; este documento solo exige que sean deterministas y documentados.
6. **Formato HTTP con CSS y JS.** La petición de que la aplicación funcione "en formato http con CSS y JS" en distintos dispositivos se cumple con el stack existente: FastAPI sirve por HTTP, en la misma URL y puerto, el build de React + TypeScript (compilado a JavaScript) con Tailwind CSS 3, y el diseño adaptable se define en el Requisito 21. No se reescribe la interfaz en HTML plano ni se agregan frameworks.
7. **Credenciales de AWS.** Las credenciales las aporta el equipo en un archivo `.env` en la raíz del proyecto (uso local, creado a mano a partir de `.env.example` y no versionado) o el rol de la tarea de AWS (despliegue). Ningún valor de credencial aparece en el repositorio, en este documento, en el código, en los registros ni en las respuestas de la API.
8. **Región de AWS.** Si el equipo define `AWS_DEFAULT_REGION`, PocketIQ no la usa; la región se toma solo de `AWS_REGION`, con valor por defecto `us-east-1`.

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
- **API**: Conjunto de endpoints HTTP del Backend bajo el prefijo `/api/`, con entradas y salidas definidas por los Esquemas.
- **Ventana_Evaluacion**: Cuadros de tracking de una jugada con `frameId` mayor que el Cuadro_Snap y menor o igual que el primero, en orden de `frameId`, de estos cuadros de fin: Cuadro_Pase, primer cuadro con evento de sack (`"qb_sack"` o `"qb_strip_sack"`) o último cuadro de tracking de la jugada. Se define en el Requisito 9, criterio 7.
- **Asistente_IA**: Módulo `backend/ai.py` que construye el Contexto_IA, invoca un modelo Amazon Nova mediante Amazon Bedrock y valida la Respuesta_IA.
- **Bedrock**: Servicio Amazon Bedrock (`bedrock-runtime`) usado por el Asistente_IA; es el único servicio de AWS que invoca PocketIQ.
- **Contexto_IA**: Objeto JSON estructurado y agregado que el Asistente_IA construye en Python a partir de la respuesta de análisis del Requisito 14: filtros aplicados, n, número de partidos, Calidad_Muestra, tasas y promedios de `summary`, `pressureMap`, `diagnoses` con su Fuente_Etiqueta, `protectionResponses` con su n y Calidad_Muestra, y `representativePlays` con `gameId` y `playId`. Es el único dato que se envía a Nova; no incluye filas de tracking, credenciales ni variables de entorno.
- **Respuesta_IA**: Salida estructurada que el modelo Amazon Nova devuelve al Asistente_IA, una vez validada por el Backend.
- **Hecho**: Afirmación de una Respuesta_IA respaldada por un valor presente en el Contexto_IA, acompañada del nombre de ese campo, su valor y su Fuente_Etiqueta.
- **Hipotesis**: Explicación propuesta en una Respuesta_IA que los datos no confirman; se marca como hipótesis y con el texto "requiere validación en video".
- **Reporte_Scouting**: Documento con secciones fijas (Requisito 27) generado por el Asistente_IA o, sin IA, por el Motor_Analitico.
- **Panel_IA**: Sección del Dashboard con las acciones de IA definidas en el Requisito 28.


## Requirements

### Requisito 1: Estructura, despliegue y rutas

**User Story:** Como equipo de desarrollo, quiero que PocketIQ respete el contrato de despliegue del hackathon, para que AWS pueda hospedar la aplicación sin cambios.

#### Acceptance Criteria

1. THE Backend SHALL exponer en `backend/main.py` una variable de módulo llamada `app` que sea una instancia de `FastAPI`, de modo que `uvicorn backend.main:app` arranque el servidor sin argumentos adicionales.
2. WHEN se recibe `GET /health`, THE Backend SHALL responder con código 200, tipo de contenido JSON y un cuerpo exactamente igual a `{"status": "ok"}`, sin claves adicionales.
3. THE Backend SHALL publicar todos los endpoints que devuelven datos, métricas, diagnósticos o resúmenes bajo el prefijo `/api/`; `GET /health` es la única ruta de API fuera de ese prefijo.
4. WHEN se recibe `GET /` o una petición a un archivo existente dentro de `dashboard/dist`, THE Backend SHALL responder con el contenido de `dashboard/dist/index.html` o del archivo pedido, en el mismo proceso, URL base y puerto que atienden `/health` y `/api/`.
5. IF se recibe una petición a una ruta bajo `/api/` que no corresponde a ningún endpoint definido, THEN THE Backend SHALL responder con código 404 y un cuerpo JSON, sin devolver el contenido de `index.html`.
6. IF el directorio `dashboard/dist` no existe al arrancar, THEN THE Backend SHALL arrancar de todos modos y responder `GET /health` y los endpoints bajo `/api/` igual que cuando el directorio existe.
7. THE Dashboard SHALL invocar la API únicamente con rutas relativas de la forma `api/<ruta>`; ninguna llamada a la API en `dashboard/src/` empieza con `/`, `http://`, `https://`, `localhost` ni `127.0.0.1`.
8. THE Dashboard SHALL referenciar imágenes, hojas de estilo y enlaces internos en `dashboard/src/` y `dashboard/index.html` solo con rutas relativas sin diagonal inicial; ninguna de esas referencias contiene `localhost`, `127.0.0.1` ni una URL absoluta con esquema `http://` o `https://`.
9. THE Dashboard SHALL conservar `base: './'` en `dashboard/vite.config.ts` y definir en el mismo archivo un proxy del servidor de desarrollo que reenvíe las peticiones con prefijo `/api` hacia `http://localhost:8000`.
10. WHEN se ejecuta `npm run build` en `dashboard/`, THE Dashboard SHALL terminar con código de salida 0, sin errores de TypeScript, y generar `dashboard/dist/index.html` con todas sus referencias a recursos en forma relativa (`./`).
11. THE PocketIQ SHALL declarar en sus manifiestos de dependencias de Python y de Node solo los paquetes listados en `.kiro/steering/rules.md`, con las versiones exactas indicadas ahí, sin agregar paquetes nuevos ni cambiar versiones.
12. THE Motor_Analitico SHALL residir en `backend/analytics.py`.
13. THE Esquemas SHALL residir en `backend/schemas.py` y definir los modelos Pydantic de entrada y salida de los endpoints bajo `/api/`.
14. WHILE el Backend está en ejecución, THE PocketIQ SHALL funcionar sin escribir archivos en disco y sin modificar ningún archivo bajo `data/`; los datos derivados se mantienen solo en memoria.

### Requisito 2: Carga de datos y manejo de memoria

**User Story:** Como entrenador ofensivo, quiero que la aplicación responda con datos reales sin agotar la memoria del servidor, para que pueda consultar cualquier rival de forma estable.

#### Acceptance Criteria

1. THE Motor_Analitico SHALL leer únicamente los archivos `data/games.csv`, `data/plays.csv`, `data/players.csv`, `data/pffScoutingData.csv` y `data/tracking/tracking_<gameId>.csv`, con rutas relativas a la raíz del proyecto, sin leer ningún otro archivo de `data/`.
2. THE Motor_Analitico SHALL abrir los archivos de `data/` solo en modo lectura, de modo que después de cualquier ejecución del Backend el conjunto de archivos de `data/`, sus tamaños y sus fechas de modificación sean idénticos a los previos al arranque.
3. WHEN el Backend arranca, THE Motor_Analitico SHALL cargar `games.csv`, `plays.csv`, `players.csv` y `pffScoutingData.csv` en memoria exactamente una vez por proceso y calcular los agregados de PFF por jugada (incluidos `passRushers`, `hasPffPressure` y `hasOffensiveCharge`) antes de responder cualquier solicitud bajo `/api/...`.
4. WHEN se solicita un análisis de un Rival cuyos agregados de tracking no están en Cache_Tracking, THE Motor_Analitico SHALL leer solo los archivos `tracking_<gameId>.csv` cuyos `gameId` aparecen en `plays.csv` con `defensiveTeam` igual a ese Rival, y SHALL mantener en memoria como máximo un DataFrame de tracking sin procesar a la vez durante ese cálculo.
5. WHEN el Motor_Analitico lee un archivo de tracking, THE Motor_Analitico SHALL cargar solo las columnas `gameId`, `playId`, `nflId`, `frameId`, `team`, `playDirection`, `x`, `y` y `event`.
6. WHEN el Motor_Analitico termina de procesar un archivo de tracking, THE Motor_Analitico SHALL conservar en memoria, para cada jugada del Rival en ese archivo, solo los agregados por jugada y las trayectorias en Coordenadas_Normalizadas de los 22 jugadores y del balón desde el Cuadro_Snap inclusive hasta el cuadro de fin de la Ventana_Evaluacion (necesarias para el detalle del Requisito 15), y SHALL liberar el DataFrame sin procesar de ese archivo antes de leer el siguiente.
7. THE Cache_Tracking SHALL almacenar los agregados de tracking por Rival y los resultados de análisis por combinación de filtros solo en memoria del proceso, de modo que al reiniciar el Backend la Cache_Tracking quede vacía.
8. WHEN se solicita un análisis de un Rival cuyos agregados de tracking ya están en Cache_Tracking, THE Motor_Analitico SHALL responder con esos agregados sin volver a leer ningún archivo de tracking, y para una misma combinación de filtros SHALL devolver un resultado idéntico al de la primera solicitud.
9. WHILE una solicitud está calculando los agregados de un Rival, THE Cache_Tracking SHALL hacer esperar a cualquier otra solicitud concurrente del mismo Rival hasta que el cálculo termine y entregarle los mismos agregados, de modo que los archivos de tracking de ese Rival se procesen como máximo una vez por proceso.
10. THE Motor_Analitico SHALL funcionar sin leer ni escribir archivos calculados previamente en disco, y SHALL producir los mismos resultados en un arranque con la Cache_Tracking vacía que en uno con la Cache_Tracking poblada.
11. THE Motor_Analitico SHALL unir games con plays por `gameId`, plays con PFF por `gameId` y `playId`, PFF con players por `nflId`, plays con tracking por `gameId` y `playId`, y PFF con tracking por `gameId`, `playId` y `nflId`.
12. THE Motor_Analitico SHALL identificar a los jugadores únicamente por `nflId`, sin unir por `displayName`.
13. IF al arrancar falta alguno de `games.csv`, `plays.csv`, `players.csv` o `pffScoutingData.csv`, no se puede leer, o le falta una columna requerida, THEN THE Backend SHALL detener el arranque con un error que identifique el archivo y, si aplica, la columna faltante.
14. IF falta o no se puede leer el archivo `tracking_<gameId>.csv` de un partido del Rival, THEN THE Motor_Analitico SHALL seguir procesando los demás archivos, excluir las jugadas de ese partido de las métricas que dependen de tracking, conservar sus métricas de PFF y observadas, e indicar en la respuesta del análisis cuántos partidos se omitieron por falta de tracking.
15. IF el cálculo de los agregados de tracking de un Rival falla antes de completarse, THEN THE Cache_Tracking SHALL quedar sin agregados parciales de ese Rival y liberar el bloqueo de ese Rival para solicitudes posteriores, y THE Backend SHALL responder con un error que indique que el análisis de tracking del Rival no se pudo completar.

### Requisito 3: Validaciones de integridad de datos

**User Story:** Como analista, quiero que la aplicación compruebe la integridad de los datos, para que pueda confiar en que las métricas no provienen de uniones o cálculos erróneos.

#### Acceptance Criteria

1. WHEN el Motor_Analitico carga `plays.csv`, THE Validador_Datos SHALL comprobar que cada llave (`gameId`, `playId`) aparece en una sola fila, conservar en la Tabla_Analitica solo la primera fila de cada llave en el orden del archivo y contar como casos afectados las filas descartadas.
2. WHEN el Motor_Analitico carga `pffScoutingData.csv`, THE Validador_Datos SHALL comprobar que cada `nflId` existe en `players.csv`, conservar la fila para los conteos de roles de PFF, dejar nulos los atributos de `players.csv` de ese jugador y contar como casos afectados las filas con `nflId` inexistente.
3. WHEN el Motor_Analitico carga `pffScoutingData.csv`, THE Validador_Datos SHALL comprobar que cada jugada tiene exactamente 11 jugadores con `pff_role` en {`"Pass Block"`, `"Pass Route"`, `"Pass"`} y exactamente 11 jugadores con `pff_role` en {`"Pass Rush"`, `"Coverage"`}, dejar nulos los conteos de Rushers y de Bloqueadores de cada jugada que no cumpla y contar como casos afectados esas jugadas.
4. WHEN el Motor_Analitico procesa un archivo de tracking, THE Validador_Datos SHALL comprobar que cada valor de `team` coincide con `possessionTeam`, `defensiveTeam` o `"football"` de la jugada, excluir las filas que no coincidan de los cálculos de tracking de esa jugada y contar como casos afectados esas filas.
5. WHEN el Motor_Analitico procesa un archivo de tracking, THE Validador_Datos SHALL comprobar que cada cuadro (`gameId`, `playId`, `frameId`) tiene exactamente una fila con `team == "football"`, excluir de los cálculos de tracking de esa jugada los cuadros con cero o más de una fila del balón y contar como casos afectados esos cuadros.
6. WHEN el Motor_Analitico calcula timeToThrow o threatTime de una jugada, THE Validador_Datos SHALL comprobar que el valor es mayor o igual a 0 segundos y que el `frameId` del Cuadro_Pase es estrictamente mayor que el `frameId` del Cuadro_Snap; si la comprobación falla, el valor de esa jugada queda nulo, no entra en ningún promedio, percentil ni conteo, y la jugada se cuenta como caso afectado.
7. IF una comprobación del Validador_Datos encuentra uno o más casos afectados, THEN THE Motor_Analitico SHALL registrar en el registro técnico del Backend una advertencia con el nombre de la comprobación, el archivo procesado y el número de casos afectados, y continuar la carga sin detener el Backend, excluyendo solo los valores, filas, cuadros o jugadas descritos en los criterios 1 a 6.
8. THE Motor_Analitico SHALL emitir como máximo una advertencia técnica por comprobación y por archivo en cada carga de datos, sin incluir contenido de filas individuales, valores de variables de entorno ni credenciales.
9. THE Motor_Analitico SHALL producir tasas con valores en el intervalo cerrado de 0 a 1 y conteos con valores enteros mayores o iguales a 0.
10. IF el denominador de una tasa es 0, THEN THE Motor_Analitico SHALL devolver esa tasa como nula en lugar de 0 o de un valor no numérico.
11. WHEN una comprobación del Validador_Datos encuentra 0 casos afectados en un archivo, THE Motor_Analitico SHALL omitir la advertencia técnica de esa comprobación para ese archivo.

### Requisito 4: Tabla analítica por jugada

**User Story:** Como entrenador ofensivo, quiero que cada jugada quede resumida en una fila con contexto, protección y presión, para que los filtros y comparaciones operen sobre una unidad consistente.

#### Acceptance Criteria

1. THE Motor_Analitico SHALL construir la Tabla_Analitica con exactamente una fila por cada par (`gameId`, `playId`) distinto presente en `data/plays.csv`, sin filas duplicadas para el mismo par, y con las columnas `gameId`, `playId`, `week`, `possessionTeam`, `defensiveTeam`, `quarter`, `gameClock`, `down`, `yardsToGo`, `distanceBand`, `fieldZone`, `offenseFormation`, `personnelO`, `personnelD`, `defendersInBox`, `playAction`, `dropBackType`, `coverage`, `coverageType`, `passResult`, `prePenaltyPlayResult`, `playResult`, `passRushers`, `passBlockers`, `hasPffPressure`, `hasHurry`, `hasHit`, `hasSack`, `hasBeatenBlocker`, `hasOffensiveCharge`, `timeToThrow`, `threatTime`, `threatSide`, `pressureSourceCandidate` y `sampleQuality`.
2. THE Motor_Analitico SHALL calcular `distanceBand` según el Requisito 6, `fieldZone` según el Requisito 5, `timeToThrow` y `threatTime` según los Requisitos 7 y 9 y el Glosario, `threatSide` según el Requisito 11, `pressureSourceCandidate` según el Requisito 12 y `sampleQuality` según la definición de Calidad_Muestra del Glosario.
3. THE Motor_Analitico SHALL calcular `passRushers` como el número entero, entre 0 y 22, de Rushers de la jugada (jugadores con `pff_role == "Pass Rush"`).
4. THE Motor_Analitico SHALL calcular `passBlockers` como el número entero, entre 0 y 22, de Bloqueadores de la jugada (jugadores con `pff_role == "Pass Block"`).
5. THE Motor_Analitico SHALL identificar como Ayuda_Chip a cada jugador con `pff_role == "Pass Route"` que tenga `pff_blockType` no nulo o `pff_nflIdBlockedPlayer` no nulo, y SHALL excluir a cada Ayuda_Chip del conteo de `passBlockers` y del conteo de `passRushers`.
6. THE Motor_Analitico SHALL marcar como Blitz_Aproximado toda jugada con `passRushers >= 5` y como no Blitz_Aproximado toda jugada con `passRushers` entre 0 y 4.
7. THE Dashboard SHALL mostrar el texto "blitz aproximado" en cada vista, filtro, leyenda o tabla donde presente el Blitz_Aproximado, sin usar la etiqueta "blitz" sin el calificativo "aproximado".
8. THE Motor_Analitico SHALL asignar `hasPffPressure` como verdadero si al menos un jugador de la jugada tiene `pff_hit`, `pff_hurry` o `pff_sack` igual a 1, y como falso si ningún jugador tiene alguno de esos campos igual a 1 y al menos un jugador tiene alguno de esos campos no nulo.
9. THE Motor_Analitico SHALL calcular cada indicador por separado: `hasHurry` como verdadero si algún jugador tiene `pff_hurry == 1`, `hasHit` como verdadero si algún jugador tiene `pff_hit == 1`, `hasSack` como verdadero si algún jugador tiene `pff_sack == 1` y `hasBeatenBlocker` como verdadero si algún jugador tiene `pff_beatenByDefender == 1`; cada indicador es falso si su campo de origen vale 0 en todos los jugadores con valor no nulo.
10. THE Motor_Analitico SHALL calcular `hasOffensiveCharge` como verdadero si algún Bloqueador tiene `pff_hitAllowed`, `pff_hurryAllowed` o `pff_sackAllowed` igual a 1, usando solo esos tres campos y sin leer `pff_hit`, `pff_hurry` ni `pff_sack`.
11. THE Motor_Analitico SHALL calcular sobre la muestra filtrada dos tasas de sack independientes, cada una como proporción entre 0 y 1: la tasa por resultado (jugadas con `passResult == "S"` dividido entre jugadas con `passResult` no nulo) y la tasa PFF (jugadas con `hasSack` verdadero dividido entre jugadas con `hasSack` no nulo), sin que ninguna de las dos tasas sustituya a la otra.
12. IF en la muestra filtrada al menos una jugada tiene `passResult == "S"` y `hasSack` falso, o `passResult != "S"` y `hasSack` verdadero, THEN THE API SHALL incluir en la respuesta la tasa por resultado, la tasa PFF y el número entero de jugadas discrepantes.
13. THE Dashboard SHALL mostrar el texto "Evento defensivo PFF (hit, hurry o sack)", identificado como definición operativa de PocketIQ, junto a cada métrica o gráfico derivado de `hasPffPressure`.
14. IF todos los jugadores de una jugada tienen nulos los campos de origen de un valor derivado (por ejemplo, `pff_hit`, `pff_hurry` y `pff_sack` para `hasPffPressure`), THEN THE Motor_Analitico SHALL guardar ese valor derivado como nulo, sin sustituirlo por cero ni por falso.
15. IF un campo de origen de nivel jugada (por ejemplo, `passResult`, `yardsToGo` o `defendersInBox`) es nulo, THEN THE Motor_Analitico SHALL guardar como nulos ese campo y cada valor derivado de él, conservando la fila de la jugada en la Tabla_Analitica.
16. IF una jugada de `data/plays.csv` no tiene filas en `data/pffScoutingData.csv`, THEN THE Motor_Analitico SHALL conservar la fila de la jugada en la Tabla_Analitica y guardar como nulos `passRushers`, `passBlockers`, `hasPffPressure`, `hasHurry`, `hasHit`, `hasSack`, `hasBeatenBlocker` y `hasOffensiveCharge`.

### Requisito 5: Zona del campo

**User Story:** Como entrenador ofensivo, quiero filtrar por la zona del campo, para que pueda estudiar cómo cambia la presión cerca de la zona roja o en campo propio.

#### Acceptance Criteria

1. WHEN el Motor_Analitico construye la fila de una jugada en la Tabla_Analitica y `yardlineNumber == 50`, THE Motor_Analitico SHALL asignar a esa jugada una distancia a la zona de anotación de 50 yardas, sin consultar `yardlineSide` (que es nulo en las 125 jugadas con `yardlineNumber == 50`).
2. WHEN el Motor_Analitico construye la fila de una jugada en la Tabla_Analitica, `yardlineNumber` es un entero de 1 a 49 y `yardlineSide == possessionTeam`, THE Motor_Analitico SHALL asignar una distancia a la zona de anotación de `100 - yardlineNumber` yardas (rango resultante: 51 a 99).
3. WHEN el Motor_Analitico construye la fila de una jugada en la Tabla_Analitica, `yardlineNumber` es un entero de 1 a 49, `yardlineSide` no es nulo y `yardlineSide != possessionTeam`, THE Motor_Analitico SHALL asignar una distancia a la zona de anotación igual a `yardlineNumber` yardas (rango resultante: 1 a 49).
4. WHEN el Motor_Analitico construye la fila de una jugada en la Tabla_Analitica y `down == 0`, THE Motor_Analitico SHALL asignar `fieldZone` = "Conversión de dos puntos", con prioridad sobre el criterio 5 e independientemente de la distancia a la zona de anotación.
5. WHEN el Motor_Analitico construye la fila de una jugada en la Tabla_Analitica, `down` está entre 1 y 4 y la distancia a la zona de anotación está entre 1 y 99, THE Motor_Analitico SHALL asignar exactamente un valor de `fieldZone` según estos rangos inclusivos: "Propio 1–20" para 80 a 99 yardas, "Propio 21–40" para 60 a 79 yardas, "Medio campo" para 40 a 59 yardas, "Territorio rival" para 21 a 39 yardas y "Zona roja" para 1 a 20 yardas.
6. IF `down` está entre 1 y 4 y `yardlineNumber` es nulo, `yardlineNumber` no es un entero de 1 a 50, o `yardlineSide` es nulo con `yardlineNumber != 50`, THEN THE Motor_Analitico SHALL asignar `fieldZone` nulo, conservar la jugada en la Tabla_Analitica con el resto de sus columnas sin cambios y registrar en las advertencias técnicas el número de jugadas afectadas por esta causa.
7. IF una jugada tiene `fieldZone` nulo, THEN THE Motor_Analitico SHALL excluirla de los resultados cuando el filtro de Zona_Campo tiene un valor distinto de "Todos" e incluirla cuando el filtro de Zona_Campo es "Todos".

### Requisito 6: Banda de distancia

**User Story:** Como entrenador ofensivo, quiero agrupar las situaciones por distancia por avanzar, para que obtenga muestras comparables sin fragmentar los datos por yarda exacta.

#### Acceptance Criteria

1. WHEN el Motor_Analitico construye la Tabla_Analitica y una jugada tiene `down == 0`, THE Motor_Analitico SHALL asignar a esa jugada la Banda_Distancia "Conversión", independientemente de su valor de `yardsToGo`.
2. WHEN el Motor_Analitico construye la Tabla_Analitica y una jugada tiene `down` entre 1 y 4, THE Motor_Analitico SHALL asignar a esa jugada exactamente una Banda_Distancia: "Corta" si `yardsToGo` está entre 1 y 3, "Media" si está entre 4 y 6, "Larga" si está entre 7 y 10, y "Muy larga" si es 11 o mayor, con ambos límites de cada rango incluidos.
3. IF una jugada con `down` distinto de 0 tiene `yardsToGo` nulo o menor que 1, THEN THE Motor_Analitico SHALL marcar la jugada como inconsistente mediante el Validador_Datos y excluirla de todo filtro por Banda_Distancia y por distancia exacta.
4. WHEN la solicitud de análisis incluye un valor de `distanceBand` distinto de nulo, THE Motor_Analitico SHALL incluir únicamente las jugadas del Rival cuya Banda_Distancia es igual a ese único valor; el valor nulo equivale a "Todos".
5. WHEN la solicitud de análisis incluye una distancia exacta entera entre 1 y 99, THE Motor_Analitico SHALL incluir únicamente las jugadas con `yardsToGo` igual a ese valor y `down` distinto de 0, ignorar el filtro por Banda_Distancia mientras la distancia exacta esté activa y devolver una respuesta con n == 0 cuando ninguna jugada tiene ese valor.
6. IF la solicitud de análisis incluye una distancia exacta que no es un número entero o que está fuera del rango de 1 a 99, THEN THE Backend SHALL rechazar la solicitud con código 422 y un mensaje de error que indique el rango válido, sin modificar los filtros aplicados previamente.
7. THE Dashboard SHALL mostrar el filtro por Banda_Distancia como opción preseleccionada y marcada como "recomendada", presentar la distancia exacta como opción secundaria que el usuario debe activar de forma explícita e indicar, mientras la distancia exacta esté activa, que el filtro por Banda_Distancia no se está aplicando.

### Requisito 7: Eventos de snap y pase y tiempo de lanzamiento

**User Story:** Como entrenador ofensivo, quiero saber cuánto tarda el QB en lanzar, para que pueda relacionar el ritmo de la jugada con la presión.

#### Acceptance Criteria

1. THE Motor_Analitico SHALL tratar la cadena literal `"None"` en la columna `event` como ausencia de evento y SHALL comparar los nombres de evento (`ball_snap`, `autoevent_ballsnap`, `pass_forward`, `autoevent_passforward`) por coincidencia exacta de texto.
2. IF una jugada tiene al menos un cuadro con `event == "ball_snap"`, THEN THE Motor_Analitico SHALL elegir el Cuadro_Snap entre los cuadros con `ball_snap` e ignorar `autoevent_ballsnap` en esa jugada.
3. IF una jugada no tiene ningún cuadro con `ball_snap` y tiene al menos un cuadro con `autoevent_ballsnap`, THEN THE Motor_Analitico SHALL elegir el Cuadro_Snap entre los cuadros con `autoevent_ballsnap`.
4. IF una jugada tiene al menos un cuadro con `event == "pass_forward"`, THEN THE Motor_Analitico SHALL elegir el Cuadro_Pase entre los cuadros con `pass_forward` e ignorar `autoevent_passforward` en esa jugada.
5. IF una jugada no tiene ningún cuadro con `pass_forward` y tiene al menos un cuadro con `autoevent_passforward`, THEN THE Motor_Analitico SHALL elegir el Cuadro_Pase entre los cuadros con `autoevent_passforward`.
6. IF una jugada tiene más de un cuadro con el evento elegido para el snap o para el pase, THEN THE Motor_Analitico SHALL tomar el cuadro de menor `frameId` de ese evento, de modo que las 3,746 jugadas con varios cuadros de snap obtengan un único Cuadro_Snap.
7. WHEN una jugada tiene Cuadro_Snap y Cuadro_Pase con `frameId` del Cuadro_Pase mayor que el `frameId` del Cuadro_Snap, THE Motor_Analitico SHALL calcular timeToThrow como `(frameId del Cuadro_Pase - frameId del Cuadro_Snap) / 10`, en segundos, sin usar la columna `time`, con resultado exacto en múltiplos de 0.1 s (por ejemplo, 25 cuadros de diferencia dan 2.5 s).
8. IF una jugada no tiene Cuadro_Snap, THEN THE Motor_Analitico SHALL asignar timeToThrow nulo y registrar el motivo "sin snap", incluidas las 24 jugadas sin evento de snap.
9. IF una jugada tiene Cuadro_Snap pero no tiene ni `pass_forward` ni `autoevent_passforward` (por ejemplo, sacks o scrambles), THEN THE Motor_Analitico SHALL asignar timeToThrow nulo, registrar el motivo "sin pase" y conservar la jugada en la Tabla_Analitica.
10. IF el `frameId` del Cuadro_Pase es menor o igual que el `frameId` del Cuadro_Snap, THEN THE Motor_Analitico SHALL asignar timeToThrow nulo y registrar el motivo "pase no posterior al snap", sin producir valores de timeToThrow negativos ni cero.
11. THE Motor_Analitico SHALL registrar para cada jugada el origen del evento de snap y el del evento de pase con uno de tres valores: "manual" (`ball_snap` o `pass_forward`), "automática" (`autoevent_ballsnap` o `autoevent_passforward`) o "ausente" (ninguno de los dos).

### Requisito 8: Normalización de coordenadas

**User Story:** Como analista, quiero que todas las jugadas se vean en la misma dirección de ataque, para que las comparaciones espaciales entre jugadas sean válidas.

#### Acceptance Criteria

1. WHEN el Motor_Analitico procesa una fila de tracking (de jugador o de balón) de una jugada con `playDirection == "right"`, THE Motor_Analitico SHALL calcular `x_norm = x` y `y_norm = y` sin redondeo, en yardas.
2. WHEN el Motor_Analitico procesa una fila de tracking (de jugador o de balón) de una jugada con `playDirection == "left"`, THE Motor_Analitico SHALL calcular `x_norm = 120 - x` y `y_norm = 53.3 - y` sin redondeo, en yardas.
3. WHEN el Motor_Analitico calcula las Coordenadas_Normalizadas de una fila de tracking, THE Motor_Analitico SHALL conservar en esa misma fila los valores originales de `x` e `y` sin modificarlos, junto a `x_norm` e `y_norm`, para depuración.
4. FOR ALL filas de tracking de una jugada con `playDirection == "left"` y `x` e `y` no nulos, aplicar dos veces la transformación del criterio 2 SHALL devolver valores que difieren de los `x` e `y` originales en 1e-6 yardas o menos (propiedad de involución).
5. IF el valor de `playDirection` de una jugada es nulo o distinto de las cadenas exactas `"left"` y `"right"` (comparación sensible a mayúsculas), THEN THE Motor_Analitico SHALL omitir el cálculo de Coordenadas_Normalizadas para todas las filas de esa jugada y excluir la jugada de los cálculos espaciales, y THE Validador_Datos SHALL contabilizar la jugada como excluida por dirección inválida.
6. IF una fila de tracking tiene `x` o `y` nulo, THEN THE Motor_Analitico SHALL asignar `x_norm` e `y_norm` nulos a esa fila y seguir normalizando las demás filas de la jugada.
7. THE Motor_Analitico SHALL usar `x_norm` e `y_norm`, y no `x` e `y`, en todos los cálculos espaciales derivados del tracking, incluidos la distancia Rusher-QB para el Cuadro_Amenaza y la asignación de Sector.

### Requisito 9: Tiempo hasta amenaza por proximidad

**User Story:** Como entrenador ofensivo, quiero saber cuánto tarda un rusher en llegar cerca del QB, para que pueda estimar el margen que tiene mi protección.

#### Acceptance Criteria

1. WHEN el Motor_Analitico procesa el tracking de una jugada que tiene Cuadro_Snap y QB identificado, THE Motor_Analitico SHALL calcular, para cada Rusher y cada cuadro de la Ventana_Evaluacion definida en el criterio 7, la distancia euclidiana entre el Rusher y el QB como `sqrt((x_norm_Rusher - x_norm_QB)^2 + (y_norm_Rusher - y_norm_QB)^2)`, en yardas, usando Coordenadas_Normalizadas.
2. WHEN al menos un Rusher está a una distancia menor o igual a 2.0 yardas del QB en algún cuadro de la Ventana_Evaluacion, THE Motor_Analitico SHALL asignar como Cuadro_Amenaza el cuadro con menor `frameId` que cumpla esa condición y calcular threatTime como `(Cuadro_Amenaza - Cuadro_Snap) / 10`, expresado en segundos con un decimal y con un valor mayor o igual a 0.1.
3. IF ningún Rusher está a una distancia menor o igual a 2.0 yardas del QB en ningún cuadro de la Ventana_Evaluacion, THEN THE Motor_Analitico SHALL asignar threatTime nulo y conservar en la Tabla_Analitica la distancia mínima alcanzada por cualquier Rusher, en yardas con dos decimales, y el tiempo desde el snap en que ocurrió, calculado como `(cuadro de la distancia mínima - Cuadro_Snap) / 10` en segundos con un decimal.
4. IF ningún Rusher está a una distancia menor o igual a 2.0 yardas del QB en la Ventana_Evaluacion, THEN THE Motor_Analitico SHALL excluir la jugada del numerador de cualquier métrica de amenaza por proximidad, sin importar cuál sea la distancia mínima, y conservarla en el denominador de las jugadas evaluables.
5. WHEN el Dashboard muestra threatTime o una métrica derivada de threatTime, THE Dashboard SHALL mostrarla con la etiqueta "tiempo hasta amenaza por proximidad", en segundos con un decimal (por ejemplo, "2.4 s"), junto con la Fuente_Etiqueta "inferida", y SHALL mostrar las jugadas con threatTime nulo como "sin amenaza por proximidad" en vez de un valor numérico.
6. IF la jugada no tiene Cuadro_Snap, no tiene QB identificado, no tiene ningún Rusher o no tiene archivo de tracking disponible, THEN THE Motor_Analitico SHALL asignar threatTime nulo, dejar nulos la distancia mínima y su tiempo, registrar en la Tabla_Analitica un motivo que indique cuál de esas cuatro condiciones ocurrió y excluir la jugada del numerador y del denominador de las métricas de amenaza por proximidad.
7. THE Motor_Analitico SHALL definir la Ventana_Evaluacion de cada jugada como los cuadros con `frameId` mayor que el Cuadro_Snap y menor o igual que el primero, en orden de `frameId`, de estos cuadros de fin: el Cuadro_Pase, el primer cuadro con evento de sack (`"qb_sack"` o `"qb_strip_sack"`) o el último cuadro de tracking de la jugada.
8. IF en un cuadro de la Ventana_Evaluacion falta la fila de tracking del QB o de un Rusher, o sus Coordenadas_Normalizadas son nulas, THEN THE Motor_Analitico SHALL omitir ese par Rusher-QB en ese cuadro para el cálculo de distancia y seguir evaluando los demás pares y cuadros.

### Requisito 10: Calidad de muestra

**User Story:** Como entrenador ofensivo, quiero ver siempre cuántas jugadas sustentan cada resultado, para que no tome decisiones con muestras pequeñas.

#### Acceptance Criteria

1. WHEN la API responde a una solicitud de análisis bajo `/api/...` (cualquier endpoint distinto de `GET /health` que devuelva métricas, Diagnosticos o resúmenes), THE API SHALL incluir en la respuesta n, el número de filas de la Tabla_Analitica que cumplen todos los filtros activos, y el número de partidos, el conteo de valores distintos de `gameId` entre esas filas.
2. WHEN una métrica, tabla o gráfica se calcula sobre un subconjunto de las n jugadas (por ejemplo, solo jugadas con Cuadro_Snap y Cuadro_Pase válidos para timeToThrow, o solo jugadas con Cuadro_Amenaza para threatTime), THE API SHALL incluir junto a ese resultado su propio n, igual al número de jugadas que entraron en su cálculo, y la Calidad_Muestra correspondiente a ese n.
3. THE Motor_Analitico SHALL asignar a cada n la Calidad_Muestra "amplia" si n >= 100, "moderada" si 30 <= n <= 99, "pequeña" si 10 <= n <= 29 e "insuficiente" si 0 <= n <= 9, de modo que cada entero n >= 0 reciba exactamente una clase.
4. WHEN el Dashboard muestra el resumen ejecutivo, una tabla o una gráfica, THE Dashboard SHALL mostrar en ese mismo bloque el valor numérico de n y el nombre de la Calidad_Muestra que la API devolvió para ese bloque.
5. IF el n de un bloque del Dashboard está entre 1 y 29, THEN THE Dashboard SHALL mostrar en ese bloque una advertencia con borde visible y texto que indique que la muestra es "pequeña" o "insuficiente" según la Calidad_Muestra, de modo que la advertencia se entienda sin depender solo del color.
6. IF n de la consulta está entre 1 y 29, THEN THE Generador_Resumen SHALL producir un resumen sin frases de recomendación categórica (frases que indiquen qué protección usar o que afirmen una tendencia del Rival como segura) y presentar los resultados solo como descripciones de lo observado acompañadas de n y la Calidad_Muestra.
7. IF n de la consulta es menor que 30 y al menos uno de los filtros semana, cobertura o distancia exacta está activo, THEN THE Dashboard SHALL mostrar un botón para ampliar filtros cuya etiqueta nombre el primer filtro activo según el orden semana, cobertura, distancia exacta.
8. WHEN el usuario pulsa el botón para ampliar filtros, THE Dashboard SHALL quitar únicamente el filtro nombrado en la etiqueta del botón, conservar los demás filtros activos y repetir la consulta a la API.
9. IF n == 0, THEN THE API SHALL devolver n = 0, número de partidos = 0, Calidad_Muestra "insuficiente", valor nulo en cada métrica numérica, listas vacías en cada colección y la lista de los filtros activos con sus valores, sin calcular ninguna división entre cero y sin responder con un error.
10. IF n == 0, THEN THE Dashboard SHALL mostrar, en lugar de las tablas y gráficas, un estado vacío que nombre cada filtro activo devuelto por la API con su valor y explique que esa combinación no tiene jugadas.

### Requisito 11: Lado de entrada de la amenaza

**User Story:** Como entrenador ofensivo, quiero saber por qué lado entra la amenaza, para que pueda ajustar la protección hacia ese lado.

#### Acceptance Criteria

1. WHEN una jugada tiene Cuadro_Amenaza, THE Motor_Analitico SHALL calcular `lateralDelta = rusher_y_norm - qb_y_norm`, en yardas y sin redondeo, con las Coordenadas_Normalizadas del Rusher que activó la amenaza y del QB en ese mismo Cuadro_Amenaza.
2. IF en el Cuadro_Amenaza más de un Rusher está a 2.0 yardas o menos del QB, THEN THE Motor_Analitico SHALL elegir como Rusher que activó la amenaza al de menor distancia euclidiana al QB en Coordenadas_Normalizadas y, si persiste el empate, al de menor `nflId`, de modo que la misma entrada produzca siempre el mismo Rusher.
3. WHEN el Motor_Analitico calcula `lateralDelta` para una jugada, THE Motor_Analitico SHALL asignar a `threatSide` el Sector "Izquierda" si `lateralDelta >= 4.0`, "Interior izquierda" si `1.5 <= lateralDelta < 4.0`, "Centro" si `-1.5 < lateralDelta < 1.5`, "Interior derecha" si `-4.0 < lateralDelta <= -1.5` y "Derecha" si `lateralDelta <= -4.0`, comparando el valor sin redondear contra estos umbrales exactos.
4. IF una jugada no tiene Cuadro_Amenaza, THEN THE Motor_Analitico SHALL asignar `threatSide` nulo y excluir esa jugada de los conteos por Sector sin excluirla de los demás cálculos de la Tabla_Analitica.
5. THE Suite_Pruebas SHALL validar, antes de que el Dashboard muestre etiquetas de Sector, que un Rusher con `y_norm` mayor que el `y_norm` del QB (lado izquierdo del QB mirando hacia la dirección de ataque normalizada) recibe "Izquierda" o "Interior izquierda", usando al menos una jugada con `playDirection == "right"` y al menos una con `playDirection == "left"` cuyo Sector esperado está documentado en la propia prueba.
6. IF la validación de orientación del criterio 5 muestra Sectores invertidos, THEN THE Motor_Analitico SHALL corregir una sola vez la transformación global de coordenadas del Requisito 8, sin ajustes por jugada, y THE Suite_Pruebas SHALL volver a ejecutar la validación del criterio 5 hasta que pase.
7. WHEN el Dashboard muestra una etiqueta de Sector o el Mapa_Presion, THE Dashboard SHALL mostrar en la misma vista un texto que indique que los Sectores son una clasificación geométrica de PocketIQ (Fuente_Etiqueta "inferida") y no una etiqueta oficial de PFF.
8. FOR ALL valores reales finitos de `lateralDelta`, THE Motor_Analitico SHALL asignar exactamente un Sector (propiedad de partición), y THE Suite_Pruebas SHALL verificarlo incluyendo los valores frontera -4.0, -1.5, 1.5 y 4.0.

### Requisito 12: Diagnóstico de protección

**User Story:** Como entrenador ofensivo, quiero ver posibles fuentes de presión por jugada, para que pueda orientar la revisión en video hacia los problemas más frecuentes.

#### Acceptance Criteria

1. WHEN el Motor_Analitico construye la Tabla_Analitica, THE Motor_Analitico SHALL asignar a cada jugada al menos una etiqueta de Diagnostico en `pressureSourceCandidate`, sin repetir una misma etiqueta dentro de la jugada y con las etiquetas siempre en el orden de los criterios 2 a 9.
2. WHEN al menos un Bloqueador de la jugada tiene `pff_beatenByDefender`, `pff_hitAllowed`, `pff_hurryAllowed` o `pff_sackAllowed` igual a 1, THE Motor_Analitico SHALL asignar el Diagnostico "Derrota individual" con Fuente_Etiqueta "PFF", tratando como 0 los valores nulos de esas columnas.
3. WHEN un Rusher tiene un `nflId` que no aparece en ningún `pff_nflIdBlockedPlayer` no nulo de los Bloqueadores ni de las Ayuda_Chip de la jugada, y ese Rusher está a 2.0 yardas o menos del QB en al menos un cuadro de la Ventana_Evaluacion del Requisito 9 (criterio 7), THE Motor_Analitico SHALL asignar el Diagnostico "Posible rusher libre" con Fuente_Etiqueta "inferida".
4. WHEN dos o más Bloqueadores de la jugada tienen el mismo valor no nulo de `pff_nflIdBlockedPlayer`, THE Motor_Analitico SHALL asignar el Diagnostico "Doble equipo" con Fuente_Etiqueta "PFF", sin contar las Ayuda_Chip como Bloqueadores.
5. WHEN el Dashboard muestra el Diagnostico "Doble equipo", THE Dashboard SHALL mostrar junto a la etiqueta, en la misma vista y sin interacción adicional, una nota que indique que el doble equipo no necesariamente se mantuvo durante toda la jugada.
6. WHEN al menos un jugador de la jugada tiene `pff_blockType == "CH"` o la jugada tiene al menos una Ayuda_Chip, THE Motor_Analitico SHALL asignar el Diagnostico "Chip o ayuda" con Fuente_Etiqueta "PFF".
7. WHEN, dentro de la Ventana_Evaluacion del Requisito 9 (criterio 7), el Bloqueador más cercano a un Rusher pasa de un Bloqueador a otro de posición adyacente (LT-LG, LG-C, C-RG o RG-RT), ese Rusher cruza lateralmente (en `y_norm`) la trayectoria de otro Rusher, y ambas condiciones se cumplen durante al menos N cuadros consecutivos, con N fijo y documentado en el diseño, THE Motor_Analitico SHALL asignar el Diagnostico "Posible intercambio o stunt" con Fuente_Etiqueta "inferida".
8. WHEN se cumplen las cuatro condiciones siguientes: timeToThrow es mayor que el umbral contextual (percentil fijo y documentado en el diseño, calculado sobre las jugadas de la muestra filtrada); la jugada no tiene el Diagnostico "Derrota individual"; threatTime es mayor que ese mismo umbral; y entre el Cuadro_Snap y el Cuadro_Amenaza el QB reduce su distancia al Rusher más cercano o sale de la bolsa según la definición geométrica documentada en el diseño, THE Motor_Analitico SHALL asignar el Diagnostico "Posible presión prolongada por movimiento o retención del QB" con Fuente_Etiqueta "inferida".
9. IF ninguno de los criterios 2 a 8 asigna una etiqueta a la jugada, THEN THE Motor_Analitico SHALL asignar como única etiqueta el Diagnostico "No determinado con los datos disponibles", sin que esta etiqueta coexista con otra etiqueta en la misma jugada.
10. IF una jugada no tiene Cuadro_Snap según el Requisito 7 o carece de tracking del QB o de los Rushers, THEN THE Motor_Analitico SHALL omitir para esa jugada los criterios 3, 7 y 8, omitir además el criterio 8 cuando la jugada tiene timeToThrow nulo, y seguir evaluando los criterios 2, 4 y 6.
11. THE Dashboard SHALL mostrar cada Diagnostico junto a su Fuente_Etiqueta ("PFF" o "inferida"), e incluir la palabra "Posible" o "heurística" en el texto visible de cada Diagnostico con Fuente_Etiqueta "inferida".
12. THE Dashboard SHALL mostrar los Diagnosticos sin términos de culpa definitiva (por ejemplo "responsable", "culpable" o "falló") asociados a un jugador, y mostrar en la vista de Diagnosticos un aviso de que las etiquetas no son asignaciones confirmadas por el equipo ni por video.
13. WHEN el Motor_Analitico procesa dos veces los mismos datos con la misma combinación de filtros, THE Motor_Analitico SHALL producir en ambas ejecuciones las mismas etiquetas de Diagnostico, en el mismo orden, para cada jugada.

### Requisito 13: Filtros

**User Story:** Como entrenador ofensivo, quiero combinar filtros de situación, para que pueda reproducir la situación que espero enfrentar contra el rival.

#### Acceptance Criteria

1. WHEN se recibe `GET /api/filters`, THE Backend SHALL responder con las listas `opponents`, `downs`, `distanceBands`, `offenseFormations`, `defensivePersonnels`, `blockerCounts`, `fieldZones`, `dropBackTypes`, `coverages` y `weeks`, cada una con los valores distintos presentes en la Tabla_Analitica, sin duplicados ni valores nulos, con las listas numéricas en orden ascendente y las de texto en orden alfabético, salvo `distanceBands` y `fieldZones`, que siguen el orden definido en los Requisitos 6 y 5.
2. THE Dashboard SHALL ofrecer los filtros Rival, down, Banda_Distancia, distancia exacta, formación ofensiva, personal defensivo, play action (Todos, Sí, No), número de Bloqueadores, Zona_Campo, tipo de dropback, cobertura ejecutada y semana, y poblar las opciones de cada filtro, excepto play action y distancia exacta, con la lista correspondiente de `GET /api/filters`.
3. THE Dashboard SHALL incluir la opción "Todos" como primera opción y valor inicial de cada filtro de selección, y enviar el valor `null` en el campo correspondiente de `POST /api/analysis` cuando "Todos" está seleccionado o la distancia exacta está vacía.
4. THE Dashboard SHALL aceptar en el filtro de distancia exacta solo enteros de 1 a 99 o el campo vacío, e impedir el envío de la consulta con una indicación visible en el filtro mientras el valor esté fuera de ese rango.
5. THE Dashboard SHALL ubicar el filtro de cobertura ejecutada en una sección separada titulada como análisis posterior, debajo de los filtros previos al snap, junto con una nota de texto que indique que la cobertura no se conoce antes del snap.
6. WHILE el ancho de la ventana del Dashboard es de 768 px o más, THE Dashboard SHALL presentar los filtros en una columna lateral visible de forma permanente.
7. WHILE el ancho de la ventana del Dashboard es menor de 768 px, THE Dashboard SHALL presentar los filtros en un panel desplegable, cerrado al cargar, que se abre y se cierra con un botón.
8. WHEN el usuario pulsa "Analizar defensa", THE Dashboard SHALL enviar una sola petición `POST api/analysis` con los valores de todos los filtros seleccionados en ese momento, y THE Backend SHALL aplicar los filtros no nulos de forma conjunta, de modo que una jugada se incluye solo si cumple todos ellos.
9. IF un filtro de `POST /api/analysis` recibe un valor del tipo correcto que no existe en la Tabla_Analitica, THEN THE Backend SHALL devolver una respuesta válida con `sample.plays == 0` y Calidad_Muestra "insuficiente", sin error 500.
10. IF un filtro de `POST /api/analysis` recibe un valor de tipo incorrecto o fuera de rango (`exactDistance` fuera de 1 a 99, `week` fuera de 1 a 8, `down` fuera de 0 a 4), THEN THE Backend SHALL devolver un error 422 que identifique el campo inválido, sin error 500.
11. IF `GET /api/filters` o `POST /api/analysis` falla o no responde, THEN THE Dashboard SHALL mostrar un mensaje de error visible y conservar los filtros seleccionados por el usuario.

### Requisito 14: Endpoint de análisis

**User Story:** Como entrenador ofensivo, quiero obtener en una sola consulta el resumen, el mapa de presión y las comparaciones, para que el dashboard se actualice de forma coherente.

#### Acceptance Criteria

1. WHEN se recibe `POST /api/analysis` con los campos `opponent`, `down`, `distanceBand`, `exactDistance`, `offenseFormation`, `defensivePersonnel`, `playAction`, `passBlockers`, `fieldZone`, `dropBackType`, `coverage` y `week`, THE Backend SHALL validar la entrada con los Esquemas, exigiendo `opponent` como texto no vacío de 1 a 10 caracteres, tratando como "Todos" cualquier otro campo ausente o nulo, y aceptando solo `down` entero de 0 a 4, `exactDistance` entero de 1 a 99, `passBlockers` entero de 0 a 11, `week` entero de 1 a 8, `distanceBand` como un único valor de texto o nulo y `playAction` booleano o nulo.
2. WHEN la entrada es válida, THE Backend SHALL responder con `filtersApplied`, `sample` (`plays`, `games`, `quality`, `warning`), `summary` (`text`, `blitzRate`, `averageRushers`, `pffPressureRate`, `hurryRate`, `hitRate`, `sackRate`, `averageThreatTime`, `averageTimeToThrow`), `pressureMap`, `diagnoses`, `rusherDistribution`, `coverageDistribution`, `protectionResponses` y `representativePlays`, donde `filtersApplied` repite los filtros usados (con "Todos" en los campos ausentes o nulos), `sample.plays` es n, `sample.games` es el número de `gameId` distintos de la muestra, `sample.quality` es la Calidad_Muestra de n, `sample.warning` es un texto no nulo cuando n < 30 y `null` cuando n >= 30, y cada tasa de `summary` está entre 0 y 1.
3. WHEN la entrada es válida, THE Backend SHALL incluir en `pressureMap` exactamente cinco elementos, uno por Sector en el orden Izquierda, Interior izquierda, Centro, Interior derecha, Derecha, cada uno con `sector`, `plays`, `share` (entre 0 y 1), `averageThreatTime`, `hurries`, `hits` y `sacks`, y con `plays`, `share`, `hurries`, `hits` y `sacks` iguales a 0 cuando un Sector tiene 0 jugadas.
4. THE Backend SHALL serializar como `null` todo valor faltante, incluidas las métricas cuyo denominador es 0 y los promedios sin valores válidos (por ejemplo, `averageThreatTime` cuando ninguna jugada tiene Cuadro_Amenaza), de modo que el JSON no contenga `NaN`, `Infinity` ni `-Infinity`.
5. IF la entrada no cumple los Esquemas, THEN THE Backend SHALL responder con código 422 y un mensaje que identifique el nombre de cada campo inválido y el motivo del rechazo, sin calcular el análisis y sin escribir en Cache_Tracking.
6. WHEN se recibe una solicitud válida cuyos filtros, después de tratar ausentes y nulos como "Todos", coinciden con una combinación ya calculada en el proceso actual del Backend, THE Motor_Analitico SHALL devolver el resultado guardado en Cache_Tracking, idéntico campo por campo al de la primera respuesta, sin volver a leer archivos de tracking.
7. WHILE el Dashboard espera la respuesta de `POST api/analysis` para un Rival cuyo primer análisis está en proceso, THE Dashboard SHALL mostrar un mensaje de estado de carga y ocultarlo en cuanto se recibe la respuesta o un error.
8. IF la entrada es válida y ninguna jugada cumple los filtros (n == 0), THEN THE Backend SHALL responder con la estructura completa del criterio 2, con `sample.plays` y `sample.games` iguales a 0, `sample.quality` igual a "insuficiente", los cinco Sectores de `pressureMap` con 0 jugadas, listas vacías en `diagnoses`, `rusherDistribution`, `coverageDistribution`, `protectionResponses` y `representativePlays`, y `null` en las métricas numéricas de `summary`.
9. IF el Motor_Analitico falla durante el cálculo de una solicitud válida, THEN THE Backend SHALL responder con un error que indique que el análisis no se pudo completar, sin incluir rutas de archivos ni trazas internas, y sin guardar un resultado parcial en Cache_Tracking.
10. IF `POST api/analysis` devuelve un error, THEN THE Dashboard SHALL mostrar un mensaje de error visible que indique si la causa fue un filtro inválido o un fallo del análisis, y conservar los filtros seleccionados por el usuario.

### Requisito 15: Detalle de jugada

**User Story:** Como entrenador ofensivo, quiero abrir una jugada y ver su tracking, para que pueda verificar visualmente el diagnóstico antes de revisarla en video.

#### Acceptance Criteria

1. WHEN se recibe `GET /api/plays/{game_id}/{play_id}` y el par (`gameId`, `playId`) existe en la Tabla_Analitica, THE API SHALL responder con código 200 e incluir la fila de la Tabla_Analitica de esa jugada (columnas del Requisito 4) como contexto, `playDescription`, y la lista de los jugadores de la jugada en PFF, cada uno con `nflId`, nombre, posición y `pff_role`.
2. WHEN la API construye las trayectorias del detalle, THE API SHALL incluir para cada jugador de la lista y para el balón un punto por cuadro con `frameId` y Coordenadas_Normalizadas (`x_norm`, `y_norm`), ordenados por `frameId` ascendente, desde el Cuadro_Snap inclusive hasta el cuadro de fin de la Ventana_Evaluacion del Requisito 9 (criterio 7) inclusive.
3. WHEN la API construye el detalle, THE API SHALL incluir la lista completa de Diagnosticos de `pressureSourceCandidate` de la jugada, cada uno con su Fuente_Etiqueta ("PFF", "observada" o "inferida"), y asignar también una Fuente_Etiqueta a cada otra etiqueta del detalle (por ejemplo `threatTime` con "inferida" y `hasPffPressure` con "PFF").
4. IF el par (`game_id`, `play_id`) no existe en la Tabla_Analitica, THEN THE API SHALL responder con código 404 y un mensaje que identifique el `game_id` y el `play_id` solicitados, sin error 500.
5. IF la jugada existe y no tiene Cuadro_Snap, THEN THE API SHALL responder con código 200, el contexto, `playDescription`, jugadores y Diagnosticos disponibles, las trayectorias como lista vacía y el motivo "sin snap".
6. WHEN la API construye el detalle, THE API SHALL incluir como eventos disponibles cada cuadro de tracking de la jugada cuyo `event` es distinto de la cadena literal `"None"`, con el nombre del evento y su `frameId`, ordenados por `frameId` ascendente, e indicar cuáles cuadros se eligieron como Cuadro_Snap y Cuadro_Pase según el Requisito 7.
7. IF `game_id` o `play_id` no es un número entero, THEN THE API SHALL responder con código 422 y un mensaje que identifique el parámetro inválido.
8. THE API SHALL serializar como `null` los valores faltantes del detalle (incluidos timeToThrow, threatTime y coordenadas ausentes), sin `NaN` ni infinitos en el JSON.

### Requisito 16: Resumen automático

**User Story:** Como entrenador ofensivo, quiero un resumen en lenguaje claro, para que pueda leer el hallazgo principal sin interpretar todas las gráficas.

#### Acceptance Criteria

1. WHEN el Motor_Analitico completa una consulta de análisis con n >= 1, THE Generador_Resumen SHALL producir el texto del resumen con una plantilla determinista, en español, con oraciones en este orden: (a) n, el Rival y la tasa de Blitz_Aproximado expresada como porcentaje con un decimal; (b) el Sector más frecuente entre las jugadas con `threatSide` no nulo y el promedio de threatTime en segundos con un decimal, calculado solo sobre las jugadas con threatTime no nulo y nombrado como "amenaza por proximidad"; (c) el Diagnostico más frecuente entre todas las etiquetas de `pressureSourceCandidate` de la muestra; (d) la Calidad_Muestra.
2. WHEN el Generador_Resumen recibe dos veces la misma combinación de filtros sobre los mismos datos, THE Generador_Resumen SHALL producir textos idénticos carácter por carácter, resolviendo los empates en "más frecuente" con el Sector según el orden Izquierda, Interior izquierda, Centro, Interior derecha, Derecha, y con el Diagnostico según el orden en que aparece en el Requisito 12.
3. THE Generador_Resumen SHALL formular toda relación entre métricas con expresiones de asociación como "se asocia con", "presentó menor tasa observada", "posible fuente", "en esta muestra" o "requiere validación en video", e incluir al menos una de ellas en cada resumen con n >= 1.
4. THE Generador_Resumen SHALL producir textos sin las frases "esta formación evita la presión", "el tackle causó el sack" ni "esta es la mejor jugada", sin las formas verbales causales "causa", "causó", "evita" o "garantiza", y sin los superlativos "la mejor" o "la peor".
5. THE Generador_Resumen SHALL generar el texto solo a partir de los valores de la consulta, sin llamar a servicios de IA generativa ni a ningún servicio externo, de modo que `summary.text` esté presente en toda respuesta de `POST /api/analysis` aunque el Asistente_IA no esté disponible.
6. WHEN 1 <= n < 30, THE Generador_Resumen SHALL añadir, como última oración del resumen, una frase que indique que la muestra es pequeña y debe interpretarse con cautela.
7. IF n == 0, THEN THE Generador_Resumen SHALL producir un resumen de una sola oración que indique que no hay jugadas comparables contra el Rival con los filtros activos, sin porcentajes, promedios, Sector ni Diagnostico.
8. IF n >= 1 y todas las jugadas de la muestra tienen threatTime nulo, THEN THE Generador_Resumen SHALL sustituir la oración (b) del criterio 1 por una frase que indique que no se detectó amenaza por proximidad en esta muestra, sin mostrar Sector ni valor numérico de threatTime, y conservar las oraciones (a), (c) y (d).
9. THE Backend SHALL entregar los textos generados por el Asistente_IA (Requisitos 24 a 27) solo en los endpoints bajo `/api/ai/`, como contenido complementario y separado de `summary.text`, sin reemplazar ni modificar el texto del Generador_Resumen.

### Requisito 17: Panel de resumen, tarjetas y mapa de presión

**User Story:** Como entrenador ofensivo, quiero ver de un vistazo las métricas clave y el mapa de presión, para que identifique rápido el patrón de ataque del rival.

#### Acceptance Criteria

1. THE Dashboard SHALL mostrar, en la parte superior de la página y en todo momento, un encabezado con el título "PocketIQ", el subtítulo "¿Cómo nos va a atacar esta defensa?" y la descripción "Herramienta de preparación ofensiva basada en tendencias históricas de presión, protección y tracking.", con esos textos exactos.
2. WHEN el Dashboard recibe una respuesta de análisis válida de la API, THE Dashboard SHALL mostrar en el resumen ejecutivo el texto de `summary.text` sin modificarlo, el número de jugadas n (`sample.plays`), el número de partidos (`sample.games`) y la Calidad_Muestra (`sample.quality`) de esa misma respuesta.
3. WHEN el Dashboard recibe una respuesta de análisis válida de la API, THE Dashboard SHALL mostrar ocho tarjetas con estos rótulos y valores: "Blitz aproximado" (`blitzRate`, Fuente_Etiqueta "inferida"), "Rushers promedio" (`averageRushers`, Fuente_Etiqueta "PFF"), "Evento defensivo PFF" (`pffPressureRate`, Fuente_Etiqueta "PFF"), "Tiempo promedio hasta amenaza" (`averageThreatTime`, Fuente_Etiqueta "inferida"), "Hurry rate" (`hurryRate`, Fuente_Etiqueta "PFF"), "Hit rate" (`hitRate`, Fuente_Etiqueta "PFF"), "Sack rate" (`sackRate`, calculada con `passResult == "S"`, Fuente_Etiqueta "observada") y "Tiempo promedio de lanzamiento" (`averageTimeToThrow`, Fuente_Etiqueta "observada"), cada una con su Fuente_Etiqueta visible como texto dentro de la tarjeta.
4. WHEN la tasa de sack por `passResult == "S"` y la tasa de sack PFF (`hasSack`) difieren en la respuesta según el Requisito 4 (criterios 11 y 12), THE Dashboard SHALL mostrar en la tarjeta "Sack rate", como texto secundario, la tasa de sack PFF con Fuente_Etiqueta "PFF" y el número de jugadas discrepantes.
5. THE Dashboard SHALL formatear las tasas de las tarjetas y la participación de cada Sector como porcentaje con un decimal (por ejemplo, "37.5%"), los tiempos (threatTime y timeToThrow) en segundos con un decimal seguidos de "s" (por ejemplo, "2.4 s"), los rushers promedio con un decimal y los conteos (n, hurries, hits, sacks) como enteros.
6. IF un valor de una tarjeta o de un Sector llega como `null` en la respuesta de la API, THEN THE Dashboard SHALL mostrar el texto "sin datos" en lugar del número, sin mostrar 0, "NaN" ni una celda vacía, y conservar visibles el rótulo y la Fuente_Etiqueta.
7. THE Mapa_Presion SHALL dibujar en SVG, sin dependencias adicionales a las del stack definido, exactamente cinco Sectores con los rótulos de texto Izquierda, Interior izquierda, Centro, Interior derecha y Derecha, ordenados de izquierda a derecha desde la perspectiva de la ofensiva.
8. WHEN el Dashboard recibe una respuesta de análisis válida de la API, THE Mapa_Presion SHALL mostrar en cada uno de los cinco Sectores, como texto numérico, la participación (`share`), el threatTime promedio (`averageThreatTime`), hurries, hits, sacks y n (`plays`) de ese Sector en `pressureMap`, y usar la intensidad de color solo como indicador adicional al texto.
9. IF un Sector tiene 0 jugadas en `pressureMap`, THEN THE Mapa_Presion SHALL dibujar ese Sector con su rótulo, n igual a 0, participación "0.0%" y threatTime promedio "sin datos", con la intensidad de color más baja de la escala.
10. THE Mapa_Presion SHALL mostrar, junto al SVG y visible sin interacción del usuario, la leyenda con el texto exacto "Los sectores representan la posición del rusher respecto del QB en el primer cuadro de amenaza por proximidad."
11. IF la solicitud de análisis a la API falla o devuelve un error, THEN THE Dashboard SHALL mostrar en el área del resumen un mensaje de error que indique que no se pudo cargar el análisis, y ocultar los valores de tarjetas y del Mapa_Presion que no correspondan a una respuesta válida.

### Requisito 18: Tendencias defensivas y diagnóstico en el dashboard

**User Story:** Como entrenador ofensivo, quiero ver la distribución de rushers, coberturas y diagnósticos, para que entienda el repertorio del rival.

#### Acceptance Criteria

1. WHEN el Dashboard recibe una respuesta de análisis con n >= 1, THE Dashboard SHALL mostrar con Recharts una gráfica de barras con el número y el porcentaje de jugadas para cada valor de `passRushers` presente en la muestra filtrada, y la frecuencia de Blitz_Aproximado como (jugadas con Blitz_Aproximado / n) × 100, redondeada a un decimal.
2. WHEN el Dashboard recibe una respuesta de análisis con n >= 1, THE Dashboard SHALL mostrar el diagnóstico de protección como tabla o gráfica de barras con las siete categorías de Diagnostico ("Derrota individual", "Posible rusher libre", "Doble equipo", "Chip o ayuda", "Posible intercambio o stunt", "Posible presión prolongada por movimiento o retención del QB" y "No determinado con los datos disponibles"), incluidas las categorías con 0 jugadas, y por cada categoría: número de jugadas; porcentaje calculado como (jugadas con la categoría / n) × 100 con un decimal; número de jugadas con al menos un `pff_hurry`, un `pff_hit` y un `pff_sack` igual a 1; y threatTime promedio en segundos con un decimal, calculado solo con las jugadas de la categoría que tienen Cuadro_Amenaza.
3. WHEN el Dashboard muestra el diagnóstico de protección, THE Dashboard SHALL indicar junto a la tabla o gráfica que los porcentajes de las categorías pueden sumar más de 100 % porque una jugada puede tener varios Diagnosticos.
4. THE Dashboard SHALL rotular cada gráfica, tabla o leyenda de coberturas con el texto "cobertura ejecutada (PFF)".
5. WHEN el Dashboard recibe una respuesta de análisis con n >= 1, THE Dashboard SHALL mostrar con Recharts el número y el porcentaje de jugadas sobre n, con un decimal, para cada cobertura ejecutada y cada personal defensivo presentes en la muestra filtrada, ordenados de mayor a menor número de jugadas.
6. WHEN el Dashboard recibe una respuesta de análisis con n >= 1, THE Dashboard SHALL mostrar con Recharts, para cada combinación de down y Banda_Distancia presente en la muestra filtrada, el número de jugadas y la tasa de Evento_Defensivo_PFF calculada como (jugadas con Evento_Defensivo_PFF / jugadas de la combinación) × 100, con un decimal.
7. IF la respuesta de análisis tiene n == 0, THEN THE Dashboard SHALL mostrar en lugar de las gráficas y la tabla de este requisito un mensaje indicando que no hay jugadas para los filtros seleccionados, y conservar los filtros seleccionados.
8. IF ninguna jugada de una categoría de Diagnostico tiene Cuadro_Amenaza, THEN THE Dashboard SHALL mostrar el threatTime promedio de esa categoría como "sin datos" en lugar de un valor numérico.

### Requisito 19: Respuesta ofensiva

**User Story:** Como entrenador ofensivo, quiero comparar alternativas de protección contra este rival, para que elija qué opciones revisar en video.

#### Acceptance Criteria

1. WHEN se recibe `POST /api/analysis` válido, THE API SHALL incluir en `protectionResponses` seis dimensiones de comparación, calculadas solo sobre las jugadas del Rival que cumplen todos los filtros activos: formación ofensiva (una alternativa por cada valor distinto de `offenseFormation`), número de Bloqueadores (una alternativa por cada valor distinto de `passBlockers`), play action (alternativas "Play action" para `playAction` verdadero y "Convencional" para `playAction` falso), tipo de dropback (una alternativa por cada valor distinto de `dropBackType`, incluidos los valores de rollout izquierdo y rollout derecho cuando aparecen en la muestra), tipo de bloqueo y personal ofensivo (una alternativa por cada valor distinto de `personnelO`).
2. THE API SHALL generar alternativas únicamente para valores con n >= 1 en la muestra filtrada y excluir de una dimensión las jugadas cuyo valor para esa dimensión es nulo, sin excluirlas de las demás dimensiones.
3. THE Motor_Analitico SHALL comparar el tipo de bloqueo a nivel jugada asignando una jugada a la alternativa de tipo de bloqueo X cuando al menos un Bloqueador de la jugada tiene `pff_blockType == X`, de modo que una misma jugada puede contar en varias alternativas de esta dimensión, y THE Dashboard SHALL indicar junto a esta dimensión que los porcentajes no suman 100 % por ese motivo.
4. THE API SHALL incluir por alternativa: n (número de jugadas), tasa de Evento_Defensivo_PFF (jugadas con `hasPffPressure` / n), tasa de sack observada (jugadas con `passResult == "S"` / n), threatTime promedio en segundos, tasa de pases completos (jugadas con `passResult == "C"` / n), yardas promedio de `prePenaltyPlayResult`, yardas promedio de `playResult` y Calidad_Muestra calculada con el n de la alternativa.
5. THE Motor_Analitico SHALL calcular el threatTime promedio de cada alternativa solo con las jugadas cuyo threatTime no es nulo.
6. IF todas las jugadas de una alternativa tienen threatTime nulo, THEN THE API SHALL devolver `null` en el threatTime promedio de esa alternativa sin excluir la alternativa.
7. WHEN el Dashboard muestra `protectionResponses`, THE Dashboard SHALL ordenar inicialmente las alternativas de cada dimensión de menor a mayor tasa de Evento_Defensivo_PFF, con empates ordenados de mayor a menor n.
8. WHEN el usuario pulsa el encabezado de una columna, THE Dashboard SHALL ordenar las alternativas de cada dimensión por esa columna en orden ascendente, invertir a descendente con una segunda pulsación consecutiva sobre el mismo encabezado y colocar los valores `null` al final en ambos órdenes.
9. IF una alternativa tiene n < 30, THEN THE Dashboard SHALL mostrar esa alternativa sin la palabra "recomendación" y con la advertencia de muestra pequeña definida en el Requisito 10 (borde y texto, además del color), indicando su Calidad_Muestra "pequeña" o "insuficiente".

### Requisito 20: Jugadas representativas

**User Story:** Como entrenador ofensivo, quiero ejemplos concretos del patrón, para que pueda ir directo a las jugadas que vale la pena revisar.

#### Acceptance Criteria

1. WHEN se recibe `POST /api/analysis` con una combinación de filtros válida, THE API SHALL incluir en `representativePlays` como máximo una jugada por cada una de estas cinco categorías, tomada solo de las jugadas de la Tabla_Analitica que cumplen esos filtros: "típica", "amenaza temprana", "sack", "protección exitosa comparable" y "Posible intercambio o stunt o Posible rusher libre", de modo que `representativePlays` contiene entre 0 y 5 entradas.
2. THE API SHALL identificar cada entrada de `representativePlays` con su categoría, `gameId` y `playId`, permitiendo que una misma jugada aparezca en más de una categoría.
3. THE Motor_Analitico SHALL elegir la jugada de cada categoría con una regla determinista documentada en el diseño y, si varias jugadas empatan, elegir la de menor `gameId` y, dentro del mismo `gameId`, la de menor `playId`, de modo que la misma combinación de filtros sobre los mismos datos devuelva siempre las mismas jugadas.
4. THE Motor_Analitico SHALL considerar candidatas para la categoría "sack" solo las jugadas con `passResult == "S"` (resultado observado), y para la categoría "Posible intercambio o stunt o Posible rusher libre" solo las jugadas que tienen asignado al menos uno de esos dos Diagnosticos según el Requisito 12.
5. THE Dashboard SHALL mostrar por cada jugada representativa su categoría, partido y semana, down y distancia, formación, personal defensivo, número de Rushers y de Bloqueadores, cobertura, timeToThrow, threatTime, resultado, descripción, Diagnosticos con su Fuente_Etiqueta y nivel de confianza.
6. IF timeToThrow, threatTime u otro campo de una jugada representativa es nulo, THEN THE Dashboard SHALL mostrar ese campo como no disponible en lugar de un valor numérico o vacío.
7. THE Motor_Analitico SHALL derivar el nivel de confianza de cada jugada representativa solo de la Fuente_Etiqueta de sus Diagnosticos, con esta regla determinista: "alto" si todos los Diagnosticos tienen Fuente_Etiqueta "PFF" u "observada"; "medio" si hay al menos un Diagnostico "PFF" u "observada" y al menos uno "inferida"; "bajo" si todos los Diagnosticos tienen Fuente_Etiqueta "inferida" o el único Diagnostico es "No determinado con los datos disponibles".
8. WHEN el usuario selecciona una jugada representativa, THE Dashboard SHALL pedir `api/plays/{game_id}/{play_id}` (ruta relativa al endpoint `GET /api/plays/{game_id}/{play_id}`) con el `gameId` y el `playId` de esa jugada y abrir su detalle de tracking según el Requisito 15.
9. IF la petición del detalle de una jugada representativa falla o responde 404, THEN THE Dashboard SHALL mostrar un mensaje de error que indique que el detalle no está disponible y conservar la lista de jugadas representativas visible sin cambios.
10. IF una categoría no tiene jugadas candidatas en la muestra filtrada, THEN THE API SHALL omitir esa categoría de `representativePlays`, y THE Dashboard SHALL mostrar en su lugar el nombre de la categoría con la indicación de que no hay ejemplos en la muestra.

### Requisito 21: Diseño visual y accesibilidad

**User Story:** Como entrenador ofensivo, quiero una interfaz legible tipo sala de análisis, para que pueda usarla en una reunión de preparación en pantalla grande o en móvil.

#### Acceptance Criteria

1. THE Dashboard SHALL aplicar sus estilos únicamente con clases utilitarias y configuración de Tailwind CSS 3, sin sintaxis exclusiva de Tailwind CSS 4.
2. THE Dashboard SHALL usar como fondo de página un tono 800, 900 o 950 de la paleta gris de Tailwind CSS 3 (slate, gray, zinc, neutral o stone), y un tono verde (green o emerald) como color secundario en encabezados, bordes de panel o el campo del Mapa_Presion.
3. THE Dashboard SHALL representar en toda la interfaz las amenazas (Rusher, Cuadro_Amenaza, threatTime, Evento_Defensivo_PFF y la intensidad de los Sectores del Mapa_Presion) con tonos rojo o naranja, y la protección (Bloqueador, Ayuda_Chip y respuestas de protección) con tonos azules, sin que ningún elemento de un grupo use el color del otro grupo.
4. THE Dashboard SHALL acompañar cada elemento cuyo significado se transmite por color, incluidos los Sectores del Mapa_Presion, las series de Recharts, la Calidad_Muestra y la Fuente_Etiqueta, con al menos un indicador no cromático (etiqueta de texto, porcentaje, icono de texto o CSS, patrón o borde) que baste para distinguir cada categoría con la pantalla en escala de grises.
5. THE Dashboard SHALL mostrar el texto normal con una relación de contraste de al menos 4.5:1 contra su fondo, y el texto de 18.66 px o más en negrita, el de 24 px o más y los indicadores gráficos (sectores, barras, líneas, bordes de estado) con una relación de al menos 3:1.
6. WHILE el ancho del viewport esté entre 360 px y 767 px, THE Dashboard SHALL presentar los paneles en una sola columna, sin desplazamiento horizontal de la página y con texto de al menos 14 px.
7. WHILE el ancho del viewport sea de 1024 px o más, THE Dashboard SHALL presentar los paneles en dos o más columnas y, a 1920 × 1080 px, mostrar el Mapa_Presion y los filtros activos sin desplazamiento vertical.
8. WHEN el Dashboard se carga desde el Backend, THE Dashboard SHALL hacer peticiones solo al mismo origen y puerto de PocketIQ, sin imágenes, fuentes, hojas de estilo ni scripts de dominios externos.
9. THE Dashboard SHALL referenciar sus recursos estáticos y sus llamadas a la API con rutas relativas compatibles con `base: './'`, escribiendo las llamadas a la API como `api/...` sin diagonal inicial y sin URLs absolutas con esquema y host.

### Requisito 22: Pruebas automatizadas

**User Story:** Como equipo de desarrollo, quiero pruebas que cubran las reglas analíticas, para que los cambios no rompan las definiciones.

#### Acceptance Criteria

1. THE Suite_Pruebas SHALL probar los endpoints con httpx contra `app` de `backend/main.py` y comprobar, como mínimo: que `GET /health` responde con código 200; que `GET /api/filters` responde con código 200 y una lista no vacía de Rivales; que `POST /api/analysis` con una consulta válida responde con código 200, con todas las claves del Requisito 14 (criterio 2) y con los cinco Sectores en `pressureMap`; y que `POST /api/analysis` con una consulta sin resultados responde con código 200, n == 0, métricas nulas y listas vacías según el Requisito 10 (criterio 9).
2. THE Suite_Pruebas SHALL probar la Banda_Distancia, la Zona_Campo y la Calidad_Muestra con casos en cada valor límite: `yardsToGo` 3, 4, 6, 7, 10 y 11 con `down != 0`, y cualquier `yardsToGo` con `down == 0` ("Conversión"); distancias a la zona de anotación 20, 21, 39, 40, 59, 60, 79 y 80, `yardlineNumber == 50`, `down == 0` ("Conversión de dos puntos") y `yardlineSide` nulo con `yardlineNumber != 50` (`fieldZone` nulo); y n igual a 0, 9, 10, 29, 30, 99 y 100 para la Calidad_Muestra, comparando cada resultado con la etiqueta exacta definida en los Requisitos 5, 6 y 10.
3. THE Suite_Pruebas SHALL comprobar que ninguna de las respuestas JSON del criterio 1, incluida la consulta con n == 0, contiene los literales `NaN`, `Infinity` ni `-Infinity`, decodificando el cuerpo con un analizador que falle ante esos literales.
4. THE Suite_Pruebas SHALL construir en memoria las muestras de las pruebas unitarias (filas de PFF, de jugadas y de tracking) y ejecutar esas pruebas sin abrir ningún archivo bajo `data/tracking/`.
5. FOR ALL valores de `yardsToGo` de 1 a 99 con `down` de 1 a 4, THE Motor_Analitico SHALL asignar exactamente una Banda_Distancia (propiedad de partición), y THE Suite_Pruebas SHALL verificarlo con parametrización de las 396 combinaciones, comprobando que el resultado no es nulo y coincide con el rango del Requisito 6 (criterio 2).
6. FOR ALL distancias a la zona de anotación de 1 a 99 con `down` de 1 a 4, THE Motor_Analitico SHALL asignar exactamente una Zona_Campo (propiedad de partición), y THE Suite_Pruebas SHALL verificarlo con parametrización de las 396 combinaciones, comprobando que el resultado no es nulo y coincide con el rango del Requisito 5 (criterio 5).
7. FOR ALL conjuntos de filtros, THE Motor_Analitico SHALL devolver tasas nulas o entre 0 y 1 (inclusive) y conteos enteros mayores o iguales a 0 (invariante), y THE Suite_Pruebas SHALL verificarlo sobre al menos 50 conjuntos de filtros generados con una semilla fija sobre una Tabla_Analitica construida en memoria, revisando todas las tasas y los `share` de `summary` y `pressureMap` y todos los conteos de la respuesta, y mostrando en el mensaje de fallo el conjunto de filtros que incumple la propiedad.
8. FOR ALL conjuntos de filtros, agregar un filtro adicional SHALL producir un n menor o igual al n sin ese filtro (propiedad metamórfica), y THE Suite_Pruebas SHALL verificarlo sobre al menos 50 pares (conjunto base, conjunto base más un filtro) generados con una semilla fija, mostrando en el mensaje de fallo ambos conjuntos de filtros.
9. THE Suite_Pruebas SHALL probar la selección de eventos y el tiempo de lanzamiento con estos casos: una jugada con `ball_snap` y `autoevent_ballsnap` en cuadros distintos usa el cuadro de `ball_snap`; una jugada con solo `autoevent_ballsnap` usa ese cuadro y registra marca automática; una jugada con dos cuadros `ball_snap` usa el de menor `frameId`; la cadena `"None"` en `event` cuenta como ausencia de evento; Cuadro_Snap 10 y Cuadro_Pase 35 dan timeToThrow igual a 2.5; una jugada sin snap o sin pase da timeToThrow nulo con el motivo "sin snap" o "sin pase"; y las mismas reglas de prioridad se cumplen para `pass_forward` y `autoevent_passforward`.
10. THE Suite_Pruebas SHALL probar la normalización, el Blitz_Aproximado, los Diagnosticos y el manejo de faltantes con estos casos: `x = 10`, `y = 5` dan `x_norm = 110` y `y_norm = 48.3` con `playDirection == "left"` y conservan los valores con `"right"`, con tolerancia de 1e-6; `passRushers` igual a 4 no es Blitz_Aproximado y 5 sí lo es; dos Bloqueadores con el mismo `pff_nflIdBlockedPlayer` producen "Doble equipo" y uno solo no lo produce; un Rusher ausente de todos los `pff_nflIdBlockedPlayer` que llega a 2.0 yardas del QB produce "Posible rusher libre", y el mismo Rusher a 2.01 yardas como mínimo o un Rusher bloqueado a 2.0 yardas no lo producen; y un campo de origen nulo produce un valor derivado nulo y no cero.
11. THE Suite_Pruebas SHALL usar solo pytest 8.3.5 y httpx 0.28.1 como dependencias de pruebas y generar los casos de propiedad (criterios 5 a 8) con parametrización de pytest o con un generador pseudoaleatorio de semilla fija de la biblioteca estándar de Python, de modo que dos ejecuciones consecutivas evalúen los mismos casos.
12. THE Suite_Pruebas SHALL probar el Asistente_IA sustituyendo el cliente de Bedrock por un doble de prueba, sin llamadas de red reales y sin credenciales, con estos casos: el identificador de modelo y la región se leen de `BEDROCK_MODEL_ID` y `AWS_REGION` y toman los valores `us.amazon.nova-pro-v1:0` y `us-east-1` cuando esas variables no existen; el cliente se crea solo con `region_name`, sin argumentos de llaves; cuando el doble de Bedrock lanza una excepción o excede el tiempo límite, los endpoints de `/api/ai/` responden con código 200 y `available` falso, y `POST /api/analysis` sigue respondiendo con código 200; con n == 0 el doble de Bedrock no recibe ninguna llamada; una recomendación sin jugada citada se rechaza o se marca según el Requisito 27; un Hecho que cita un valor ausente del Contexto_IA se descarta o se marca según el Requisito 26; y ninguna respuesta de la API ni ningún mensaje del registro técnico capturado durante las pruebas contiene los valores de prueba asignados a `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` o `AWS_SESSION_TOKEN`.

### Requisito 23: Criterios de cierre

**User Story:** Como equipo de desarrollo, quiero criterios claros de terminado, para que sepamos cuándo detener la implementación.

#### Acceptance Criteria

1. WHEN se ejecuta `sh .hackathon/setup.sh --check` desde la raíz del proyecto, THE PocketIQ SHALL pasar la verificación del entorno con código de salida 0 y sin reportar dependencias faltantes ni versiones distintas de las listadas en `.kiro/steering/rules.md`.
2. WHEN se ejecuta la Suite_Pruebas con pytest desde la raíz del proyecto dentro de `.venv`, THE Suite_Pruebas SHALL terminar con código de salida 0, con 0 pruebas fallidas, 0 errores de recolección y al menos una prueba ejecutada por cada caso listado en el Requisito 22.
3. WHEN se ejecuta `npm run build` en `dashboard/`, THE Dashboard SHALL terminar con código de salida 0, sin errores de TypeScript ni de Vite, y generar `dashboard/dist/index.html`.
4. WHEN termina la implementación, THE PocketIQ SHALL dejar todos los archivos de `data/` (`games.csv`, `plays.csv`, `players.csv`, `pffScoutingData.csv` y los 122 archivos `data/tracking/tracking_<gameId>.csv`) sin archivos nuevos ni borrados, de modo que la lista de archivos de `data/`, sus tamaños y sus fechas de modificación, comparados con un script o un listado tomado antes y después, sean idénticos.
5. WHEN el usuario selecciona en el Dashboard cualquier Rival de la lista `opponents` devuelta por `GET /api/filters`, con el resto de los filtros en "Todos", THE Dashboard SHALL mostrar, en un máximo de 60 segundos, el resumen ejecutivo, n, la Calidad_Muestra y las tarjetas del Requisito 17, con valores calculados por el Motor_Analitico a partir de los archivos de `data/` y sin datos de ejemplo ni valores fijos en el código.
6. WHEN el usuario selecciona un Rival con el resto de los filtros en "Todos", THE Dashboard SHALL mostrar un valor de n igual al número de filas de la Tabla_Analitica cuyo `defensiveTeam` coincide con ese Rival.
7. WHEN el Backend arranca con Uvicorn y `dashboard/dist` ya generado, THE PocketIQ SHALL responder `GET /health` con código 200 y `{"status": "ok"}` y servir el Dashboard en la misma URL y puerto.
8. WHILE no existe el archivo `.env` y Bedrock no está disponible, THE PocketIQ SHALL cumplir los criterios 1 a 7, y THE Dashboard SHALL mostrar el resumen ejecutivo, las tarjetas y el Mapa_Presion junto con el mensaje "IA no disponible" en el Panel_IA.
9. WHEN termina la implementación, THE PocketIQ SHALL tener 0 archivos versionados en git que contengan valores de `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` o `AWS_SESSION_TOKEN`, y `.env` SHALL figurar en `.gitignore`.
10. IF alguno de los criterios 1 a 9 no se cumple, THEN THE PocketIQ SHALL considerarse no terminada, y la implementación SHALL continuar hasta que los 9 criterios se cumplan.

### Requisito 24: Integración con Amazon Nova mediante Bedrock

**User Story:** Como equipo de desarrollo, quiero integrar Amazon Nova con las reglas del hackathon, para que AWS pueda hospedar las funciones de IA sin llaves en el código y sin que la IA sostenga el análisis.

#### Acceptance Criteria

1. THE Asistente_IA SHALL residir en `backend/ai.py` e invocar modelos Amazon Nova solo mediante Bedrock, usando únicamente strands-agents 1.64.0 o boto3 1.44.0. El archivo de dependencias del proyecto SHALL quedar sin paquetes nuevos y sin cambios de versión.
2. WHEN el Asistente_IA prepara una invocación de Bedrock, THE Asistente_IA SHALL obtener el identificador de modelo con `os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")` y la región con `os.environ.get("AWS_REGION", "us-east-1")`. El código SHALL contener como único identificador de modelo literal el valor por defecto `"us.amazon.nova-pro-v1:0"` y SHALL NOT leer `AWS_DEFAULT_REGION`.
3. WHEN el Asistente_IA crea el cliente de Bedrock, THE Asistente_IA SHALL crearlo solo con la región, como `boto3.client("bedrock-runtime", region_name=region)`, sin pasar llaves de acceso, token de sesión ni perfil como argumentos al cliente ni a una sesión de boto3.
4. THE Backend SHALL funcionar sin leer, verificar ni exigir `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` ni `AWS_SESSION_TOKEN`. El código de `backend/` SHALL NOT mencionar esos tres nombres de variable, SHALL NOT devolver un error por su ausencia y SHALL dejar que boto3 resuelva las credenciales por su cadena predeterminada: variables cargadas desde `.env` en uso local o rol de la tarea en AWS.
5. WHEN `backend/main.py` se importa, THE Backend SHALL definir y ejecutar la función `cargar_env()` con el código exacto de `.kiro/steering/rules.md`, antes de importar `backend/ai.py` y antes de cualquier uso de boto3. Esa función lee `.env` de la raíz del proyecto solo si existe, no lanza error si el archivo no existe y no sobrescribe variables de entorno ya definidas.
6. THE Backend SHALL excluir los valores de `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_SESSION_TOKEN` de todo registro técnico, mensaje de error, respuesta de la API, Contexto_IA y texto enviado a Nova.
7. THE Backend SHALL publicar los endpoints de IA bajo el prefijo `/api/ai/`, únicamente como `POST /api/ai/trends`, `POST /api/ai/diagnosis` y `POST /api/ai/scouting-report`.
8. THE Asistente_IA SHALL aplicar a cada invocación de Bedrock un tiempo límite en segundos tomado de la variable de entorno `AI_TIMEOUT_SECONDS`. IF `AI_TIMEOUT_SECONDS` no está definida, no es un número o está fuera del rango de 1 a 120, THEN THE Asistente_IA SHALL usar 30 segundos.
9. IF la invocación de Bedrock lanza una excepción, excede el tiempo límite, no encuentra credenciales, recibe un rechazo de acceso o devuelve una salida que no cumple el esquema esperado de la Respuesta_IA, THEN THE Backend SHALL responder con código 200 y un cuerpo JSON con `available` falso, `status` igual a "IA no disponible" y un `reason` genérico. El `reason` SHALL NOT contener rutas de archivos, trazas internas, nombres ni valores de credenciales. La respuesta SHALL NOT incluir Respuesta_IA parcial ni sin validar, SHALL entregarse a más tardar 5 segundos después de vencido el tiempo límite del criterio 8 y SHALL dejar sin cambios el Cache_Tracking y los resultados de `POST /api/analysis`.
10. WHEN un endpoint de `/api/ai/` responde con `available` verdadero, THE Backend SHALL incluir en la respuesta `available`, `modelId` igual al identificador obtenido en el criterio 2 para esa invocación, `sample` (n, partidos y Calidad_Muestra del Contexto_IA) y la Respuesta_IA validada.
11. IF Bedrock no está disponible por cualquiera de las condiciones del criterio 9 o por falta de credenciales en el entorno, THEN THE Backend SHALL responder `GET /health` con `{"status": "ok"}`, y `GET /api/filters`, `POST /api/analysis` y `GET /api/plays/{game_id}/{play_id}` con los mismos códigos de estado y contenidos que cuando Bedrock está disponible.
12. WHEN el Asistente_IA invoca Bedrock, THE Asistente_IA SHALL enviar a Nova solo el Contexto_IA y las instrucciones del asistente, sin filas de tracking sin procesar, sin contenido de archivos de `data/`, sin variables de entorno y sin credenciales.
13. THE PocketIQ SHALL invocar únicamente Bedrock como servicio de AWS. El código SHALL NOT crear clientes de boto3 distintos de `"bedrock-runtime"` y SHALL NOT llamar a otros servicios de AWS ni a proveedores de IA distintos de Amazon Nova.
14. WHEN el Asistente_IA construye el Contexto_IA, THE Asistente_IA SHALL obtener todos los valores numéricos del Motor_Analitico con la misma combinación de filtros, de modo que n, partidos, Calidad_Muestra y métricas sean idénticos a los de `POST /api/analysis` con esos filtros.
15. WHEN el Backend arranca o se importa `backend/main.py`, THE Backend SHALL omitir toda invocación a Bedrock y toda creación del cliente de Bedrock. THE Backend SHALL invocar Bedrock solo al atender una solicitud a uno de los endpoints del criterio 7.

### Requisito 25: Analista de tendencias

**User Story:** Como entrenador ofensivo, quiero que Nova explique los patrones del rival en una situación, para que entienda las estadísticas sin interpretar cada gráfica.

#### Acceptance Criteria

1. WHEN se recibe `POST /api/ai/trends`, THE Backend SHALL validar el cuerpo con el mismo esquema de filtros de `POST /api/analysis` (Requisito 14, criterio 1), con los mismos campos, rangos y tratamiento de campos ausentes o nulos como "Todos".
2. IF el cuerpo de `POST /api/ai/trends` no cumple el esquema de filtros del Requisito 14 (criterio 1), THEN THE Backend SHALL responder con código 422 y un mensaje que identifique el nombre de cada campo inválido y el motivo del rechazo, sin calcular el análisis, sin construir el Contexto_IA y sin invocar Bedrock.
3. WHEN la entrada de `POST /api/ai/trends` es válida y n >= 1, THE Asistente_IA SHALL calcular el análisis con el Motor_Analitico usando esos filtros, construir el Contexto_IA a partir de ese análisis y hacer una sola invocación a Nova que pida una explicación de los patrones observados usando como números solo los valores presentes en el Contexto_IA.
4. WHEN el Asistente_IA recibe de Nova una Respuesta_IA que cumple el esquema esperado y tiene `text` no vacío, THE Backend SHALL responder con código 200 y con `available` verdadero, `text` (explicación en español), `facts` (lista de Hechos, cada uno con `field`, `value` y `source`), `sample` con n, partidos y Calidad_Muestra idénticos a `sample.plays`, `sample.games` y `sample.quality` de `POST /api/analysis` con los mismos filtros, y `modelId` igual al identificador de modelo leído según el Requisito 24 (criterio 2).
5. IF un Hecho de la Respuesta_IA cita un `field` que no existe en el Contexto_IA, o un `value` numérico distinto del valor de ese campo en el Contexto_IA (se acepta como igual el valor exacto, el valor redondeado al número de decimales que cita el Hecho, o el valor multiplicado por 100 cuando el Hecho lo expresa como porcentaje), THEN THE Backend SHALL retirar ese Hecho de `facts` e incluir en la respuesta el número de Hechos retirados como entero mayor o igual a 0, igual a 0 cuando no se retira ninguno.
6. WHEN el Backend conserva un Hecho en `facts`, THE Backend SHALL asignar a su `source` la Fuente_Etiqueta ("observada", "PFF" o "inferida") que el Contexto_IA asocia al campo citado, aunque Nova haya devuelto otra fuente.
7. WHEN el Asistente_IA invoca a Nova para `POST /api/ai/trends`, THE Asistente_IA SHALL incluir en las instrucciones la orden de formular toda relación entre métricas solo con expresiones de asociación como las del Requisito 16 (criterio 3) y la lista de frases, formas verbales causales y superlativos prohibidos en el Requisito 16 (criterio 4).
8. WHEN el Backend devuelve un `text` de `POST /api/ai/trends`, THE Backend SHALL incluir `languageWarning` con valor verdadero si ese `text` contiene, sin distinguir mayúsculas de minúsculas, alguna frase, forma verbal o superlativo prohibido en el Requisito 16 (criterio 4), y con valor falso en caso contrario, sin modificar el `text` recibido de Nova.
9. IF la entrada es válida y n == 0, THEN THE Backend SHALL responder con código 200 sin invocar Bedrock, con `available` verdadero, `facts` vacío, número de Hechos retirados igual a 0, `languageWarning` falso, `sample` con n = 0, partidos = 0 y Calidad_Muestra "insuficiente", y un `text` de una sola oración que indique que no hay jugadas comparables contra el Rival con los filtros activos, sin porcentajes ni promedios.
10. IF la entrada es válida y 1 <= n < 30, THEN THE Backend SHALL incluir en la respuesta la advertencia de muestra pequeña del Requisito 10 con el mismo texto que `sample.warning` de `POST /api/analysis` para esos filtros, y THE Asistente_IA SHALL incluir en las instrucciones a Nova la orden de describir solo lo observado en esta muestra, sin recomendar una protección y sin afirmar una tendencia del Rival como segura.
11. IF el Motor_Analitico falla al calcular el análisis de una solicitud válida de `POST /api/ai/trends`, THEN THE Backend SHALL responder igual que `POST /api/analysis` en el Requisito 14 (criterio 9), sin invocar Bedrock y sin incluir rutas de archivos ni trazas internas.
12. IF la invocación de Bedrock para `POST /api/ai/trends` lanza una excepción, excede `AI_TIMEOUT_SECONDS`, no encuentra credenciales o devuelve una salida que no cumple el esquema esperado o con `text` vacío, THEN THE Backend SHALL responder según el Requisito 24 (criterio 9), con `available` falso, sin `facts` ni `text` generados por Nova, y sin alterar las respuestas de `POST /api/analysis` para esos filtros.

### Requisito 26: Asistente de diagnóstico

**User Story:** Como entrenador ofensivo, quiero que Nova proponga explicaciones de la presión separando hechos de hipótesis, para que sepa qué revisar en video y qué ya está confirmado por los datos.

#### Acceptance Criteria

1. WHEN se recibe `POST /api/ai/diagnosis`, THE Backend SHALL validar con los Esquemas que el cuerpo cumpla el esquema de filtros de `POST /api/analysis` (Requisito 14, criterio 1) y que, si se incluyen `gameId` y `playId`, ambos estén presentes y sean enteros.
2. IF el cuerpo de `POST /api/ai/diagnosis` no cumple el esquema de filtros, incluye un valor no entero en `gameId` o `playId`, o incluye solo uno de los dos campos `gameId` y `playId`, THEN THE Backend SHALL responder con código 422 que identifique cada campo inválido, sin invocar Bedrock.
3. IF el cuerpo es válido y el par `gameId` y `playId` enviado no existe en la Tabla_Analitica, THEN THE Backend SHALL responder con código 404 y un mensaje que identifique el `gameId` y el `playId` recibidos, sin invocar Bedrock.
4. WHEN la entrada es válida, el par `gameId` y `playId` (si se envió) existe en la Tabla_Analitica y n >= 1, THE Asistente_IA SHALL enviar a Nova un Contexto_IA con todos los campos definidos en el Glosario, en el que cada métrica y cada Diagnostico lleva su Fuente_Etiqueta ("observada", "PFF" o "inferida"), y, si se envió un par `gameId` y `playId`, con la fila de la Tabla_Analitica de esa jugada y sus etiquetas de `pressureSourceCandidate` con su Fuente_Etiqueta, sin filas de tracking.
5. WHEN el Asistente_IA envía el Contexto_IA a Nova, THE Asistente_IA SHALL instruirla para que (a) clasifique como Hecho solo las afirmaciones respaldadas por un campo del Contexto_IA, indicando el nombre del campo, su valor y su Fuente_Etiqueta; (b) clasifique como Hipotesis toda explicación que el Contexto_IA no confirme; y (c) no atribuya culpa definitiva a ningún jugador.
6. WHEN el Asistente_IA recibe una salida de Nova, THE Backend SHALL validarla contra un esquema estructurado definido en los Esquemas, y SHALL tratar como Bedrock no disponible (Requisito 24, criterio 9) toda salida en la que falte la lista `hechos` o la lista `hipotesis`, en la que un elemento de `hechos` no tenga `text`, `field`, `value` y `source`, en la que `source` tenga un valor distinto de "PFF", "observada" o "inferida", o en la que un elemento de `hipotesis` no tenga `text`.
7. WHEN la Respuesta_IA es válida, THE Backend SHALL responder con código 200, los campos del Requisito 24 (criterio 10) y dos listas separadas: `hechos`, donde cada elemento tiene `text`, `field` (nombre de un campo del Contexto_IA), `value` y `source` ("PFF", "observada" o "inferida"); e `hipotesis`, donde cada elemento tiene `text`, `type` igual a "hipótesis" y `validation` igual a "requiere validación en video". Ninguno de los dos objetos aparece a la vez en ambas listas.
8. IF un elemento de `hechos` tiene un `field` que no existe en el Contexto_IA o un `value` distinto del valor de ese campo en el Contexto_IA, THEN THE Backend SHALL retirarlo de `hechos` y agregarlo a `hipotesis` con `type` igual a "hipótesis", `validation` igual a "requiere validación en video" y `unverified` verdadero.
9. IF el `source` de un elemento de `hechos` es distinto de la Fuente_Etiqueta que el campo citado tiene en el Contexto_IA, THEN THE Backend SHALL reemplazar el `source` por la Fuente_Etiqueta del Contexto_IA, de modo que un dato con Fuente_Etiqueta "inferida" nunca aparezca con `source` igual a "PFF" u "observada".
10. IF un elemento de `hechos` tiene `source` igual a "inferida" y su `text` no contiene la palabra "Posible" ni la palabra "heurística" (sin distinguir mayúsculas), THEN THE Backend SHALL anteponer "Posible" al `text`, conforme al Requisito 12 (criterio 11), para que el texto no se lea como asignación confirmada por el equipo o por video.
11. IF el `text` de un elemento de `hechos` o `hipotesis` contiene, sin distinguir mayúsculas, alguno de los términos "responsable", "culpable" o "falló", o alguna de las frases o formas verbales prohibidas en el Requisito 16 (criterio 4), THEN THE Backend SHALL conservar el elemento en su lista y agregarle `languageWarning` verdadero; los elementos sin esos términos SHALL llevar `languageWarning` falso.
12. IF la entrada es válida, el par `gameId` y `playId` (si se envió) existe y n == 0, THEN THE Backend SHALL responder con código 200 sin invocar Bedrock, con `available` verdadero, `hechos` y `hipotesis` vacíos y un texto de una sola oración que indique que no hay jugadas comparables con los filtros activos.
13. IF la invocación de Bedrock falla según el Requisito 24 (criterio 9), THEN THE Backend SHALL responder según ese criterio, sin `hechos` ni `hipotesis` generados por Nova.

### Requisito 27: Generador de scouting report

**User Story:** Como entrenador ofensivo, quiero un scouting report con recomendaciones respaldadas por jugadas comparables, para que prepare el plan de protección con evidencia concreta.

#### Acceptance Criteria

1. WHEN se recibe `POST /api/ai/scouting-report` con los filtros del Requisito 14 (criterio 1), THE Backend SHALL validar la entrada con los Esquemas, aplicando las mismas reglas de tipo, rango y tratamiento de campos ausentes o nulos como "Todos" que `POST /api/analysis`, y calcular la respuesta de análisis del Requisito 14 con esos filtros antes de construir el Contexto_IA o el Reporte_Scouting.
2. WHEN la entrada es válida y n >= 1, THE Backend SHALL responder con código 200 y un Reporte_Scouting con exactamente estas seis secciones, en este orden y con estos títulos literales: "Resumen de tendencias", "Cómo entra la presión", "Diagnóstico de protección", "Recomendaciones ofensivas", "Jugadas comparables" y "Limitaciones", además de los campos `available`, `generatedBy` y `sample` (n, número de partidos y Calidad_Muestra de la consulta).
3. THE Backend SHALL incluir en cada elemento de "Recomendaciones ofensivas" al menos una jugada citada con su `gameId` y su `playId`, y la dimensión, la alternativa, el n y la Calidad_Muestra de la alternativa de `protectionResponses` que la respalda, con el n y la Calidad_Muestra iguales a los valores de esa alternativa en la respuesta de análisis; THE Backend SHALL considerar válida una jugada citada solo si el par (`gameId`, `playId`) pertenece a `representativePlays` o a la muestra filtrada de la consulta.
4. IF un elemento de "Recomendaciones ofensivas" no cita ninguna jugada válida según el criterio 3, cita una dimensión o alternativa ausente de `protectionResponses`, o declara un n o una Calidad_Muestra distintos de los de esa alternativa, THEN THE Backend SHALL retirar ese elemento del reporte, conservar los demás elementos sin cambios e incluir en la sección "Limitaciones" el número de elementos retirados, incluido el valor 0 cuando no se retira ninguno.
5. IF la alternativa que respalda un elemento de "Recomendaciones ofensivas" tiene n < 30 (Calidad_Muestra "pequeña" o "insuficiente"), THEN THE Backend SHALL etiquetar ese elemento como "observación con muestra pequeña", mostrar su Calidad_Muestra y excluir la palabra "recomendación" del texto de ese elemento; THE Backend SHALL usar la etiqueta "recomendación" solo en elementos cuya alternativa tiene n >= 30.
6. THE Backend SHALL incluir en la sección "Limitaciones" la Calidad_Muestra de la consulta, la aclaración de que los Diagnosticos con Fuente_Etiqueta "inferida" no son asignaciones confirmadas por el equipo ni por video, y el texto literal "requiere validación en video".
7. THE Backend SHALL marcar con `languageWarning` verdadero cada sección del Reporte_Scouting generado por Nova que contenga al menos una de las frases, formas verbales causales o superlativos prohibidos en el Requisito 16 (criterio 4), y con `languageWarning` falso cada sección que no contenga ninguno.
8. IF Bedrock no está disponible según el Requisito 24 (criterio 9), THEN THE Backend SHALL responder con código 200, `available` falso, `status` igual a "IA no disponible", el `reason` genérico del Requisito 24 (criterio 9) y un Reporte_Scouting determinista con las mismas seis secciones del criterio 2, construido por el Motor_Analitico solo a partir de la respuesta de análisis, sin invocar de nuevo Bedrock y con `generatedBy` igual a "sin IA".
9. WHEN el Reporte_Scouting proviene de Nova y supera las validaciones de los criterios 3 a 5, THE Backend SHALL asignar `generatedBy` igual a "Amazon Nova", `available` verdadero e incluir `modelId` con el identificador del modelo usado.
10. WHEN el Motor_Analitico genera dos veces el Reporte_Scouting determinista con la misma combinación de filtros sobre los mismos datos, THE Motor_Analitico SHALL producir reportes idénticos carácter por carácter, incluido el orden de los elementos de cada sección.
11. IF n == 0, THEN THE Backend SHALL responder con código 200 sin invocar Bedrock, con `generatedBy` igual a "sin IA" y un Reporte_Scouting con las seis secciones del criterio 2, todas vacías salvo "Limitaciones", que indica que no hay jugadas comparables contra el Rival con los filtros activos.
12. IF la entrada de `POST /api/ai/scouting-report` no cumple los Esquemas, THEN THE Backend SHALL responder con código 422 que identifique cada campo inválido, sin calcular la respuesta de análisis, sin invocar Bedrock y sin devolver un Reporte_Scouting.
13. WHEN el Motor_Analitico construye el Reporte_Scouting determinista, THE Motor_Analitico SHALL generar en "Recomendaciones ofensivas" como máximo un elemento por alternativa de `protectionResponses`, solo para alternativas que puedan citar al menos una jugada válida según el criterio 3, aplicar las reglas de los criterios 3 a 6, y redactar todas las secciones sin las frases, formas verbales causales ni superlativos prohibidos en el Requisito 16 (criterio 4), de modo que cada sección tenga `languageWarning` falso.
14. WHEN la entrada es válida y n >= 1, THE Backend SHALL incluir en la sección "Jugadas comparables" cada jugada citada en "Recomendaciones ofensivas" y cada jugada de `representativePlays`, una sola vez cada una, con su `gameId` y su `playId`, ordenadas por `gameId` ascendente y luego por `playId` ascendente.

### Requisito 28: Panel de IA en el dashboard

**User Story:** Como entrenador ofensivo, quiero usar los tres asistentes de IA desde el dashboard en cualquier dispositivo, para que lea las explicaciones junto a las métricas sin perder el análisis cuando la IA falla.

#### Acceptance Criteria

1. THE Dashboard SHALL mostrar un Panel_IA con tres acciones rotuladas "Explicar tendencias", "Asistente de diagnóstico" y "Generar scouting report", cada una con su propia área de resultado dentro del Panel_IA.
2. WHEN el usuario activa una acción del Panel_IA, THE Dashboard SHALL enviar una sola petición POST con `fetch` a `api/ai/trends`, `api/ai/diagnosis` o `api/ai/scouting-report` respectivamente, usando rutas relativas sin diagonal inicial ni URL absoluta, y con un cuerpo JSON que contenga los filtros seleccionados en ese momento con el mismo formato que `POST api/analysis` (Requisito 14, criterio 1).
3. WHEN el Dashboard recibe la respuesta de una acción del Panel_IA, THE Dashboard SHALL reemplazar en el área de resultado de esa acción el resultado anterior de la misma acción, sin modificar las áreas de resultado de las otras dos acciones.
4. WHILE el Dashboard espera la respuesta de una acción del Panel_IA, THE Dashboard SHALL mostrar en el área de resultado de esa acción un indicador de carga con texto visible (por ejemplo, "Generando…"), desactivar el control de esa acción hasta recibir la respuesta o un error, y mantener operables los filtros, las otras dos acciones del Panel_IA y el resto del Dashboard.
5. WHEN el Dashboard muestra un texto con `generatedBy` igual a "Amazon Nova" o una respuesta de los endpoints `/api/ai/` con `available` verdadero, THE Dashboard SHALL mostrar junto al texto, en el mismo bloque, la etiqueta de texto visible "Generado por IA (Amazon Nova) – requiere validación".
6. WHEN el Dashboard muestra la respuesta del Analista de tendencias con `available` verdadero, THE Dashboard SHALL mostrar el `text`, la lista de `facts` con el `field`, el `value` y la Fuente_Etiqueta (`source`) de cada Hecho, el n, el número de partidos y la Calidad_Muestra, y, cuando la respuesta los incluya, el número de Hechos retirados y la advertencia de muestra pequeña del Requisito 25 (criterio 10).
7. WHEN el Dashboard muestra la respuesta del Asistente de diagnóstico con `available` verdadero, THE Dashboard SHALL mostrar `hechos` e `hipotesis` en dos bloques separados con los encabezados de texto "Hechos" e "Hipótesis", la Fuente_Etiqueta de cada Hecho como texto y el texto "requiere validación en video" en cada Hipotesis, de modo que ambos bloques se distingan sin depender del color; si una de las dos listas llega vacía, su bloque SHALL mostrar el encabezado y un texto que indique que no hay elementos.
8. WHEN una respuesta del Panel_IA cita una jugada por `gameId` y `playId`, THE Dashboard SHALL mostrar cada jugada citada con su `gameId` y `playId` como texto y un control que, al activarse, pide `api/plays/{game_id}/{play_id}` con ruta relativa sin diagonal inicial y abre su detalle de tracking según el Requisito 15; si esa petición responde con error (incluido el código 404 del Requisito 15, criterio 4), THE Dashboard SHALL mostrar un mensaje que indique que el detalle de esa jugada no está disponible y conservar visible la respuesta del Panel_IA.
9. IF una respuesta de `/api/ai/` tiene `available` falso, o la petición falla por error de red, por un código HTTP distinto de 200 (incluido 422) o por un cuerpo que no es JSON válido, THEN THE Dashboard SHALL mostrar en el área de resultado de esa acción el mensaje "IA no disponible", volver a activar el control de esa acción para permitir un nuevo intento, conservar los filtros seleccionados y mantener visibles y sin cambios el resumen ejecutivo, las tarjetas, el Mapa_Presion, las gráficas, los filtros y los resultados de las otras acciones del Panel_IA.
10. WHEN el Dashboard recibe de `api/ai/scouting-report` un Reporte_Scouting con `generatedBy` igual a "sin IA", THE Dashboard SHALL mostrar el mensaje "IA no disponible" y, debajo, el Reporte_Scouting determinista completo con sus seis secciones en el orden del Requisito 27 (criterio 2) y la etiqueta de texto visible "Reporte determinista sin IA", sin mostrar la etiqueta "Generado por IA (Amazon Nova) – requiere validación".
11. WHEN el Dashboard muestra un Reporte_Scouting, THE Dashboard SHALL ofrecer una acción "Copiar" que copia al portapapeles el texto de las seis secciones con sus títulos y una acción "Imprimir" que abre el diálogo de impresión del navegador, usando solo APIs nativas del navegador y sin dependencias nuevas.
12. IF la copia al portapapeles falla o la API de portapapeles del navegador no está disponible (por ejemplo, en una página servida por HTTP sin contexto seguro), THEN THE Dashboard SHALL mostrar un mensaje visible que indique que no se pudo copiar el reporte, mantener visible el Reporte_Scouting y mantener disponible la acción "Imprimir".
13. WHEN el Dashboard muestra un `text`, un Hecho, una Hipotesis o una sección del Reporte_Scouting con `languageWarning` verdadero o `unverified` verdadero, THE Dashboard SHALL mostrar ese elemento con un borde visible y un texto de advertencia junto al elemento: "Advertencia: lenguaje a revisar" para `languageWarning` y "No verificado en los datos" para `unverified`, con ambos textos cuando los dos marcadores son verdaderos.
14. THE Panel_IA SHALL cumplir los Requisitos 21 (criterios 4 a 7): entre 360 px y 767 px de ancho de viewport, presentarse en una sola columna, sin desplazamiento horizontal de la página, con texto de al menos 14 px y con las tres acciones visibles sin desplazamiento horizontal; y a 1024 px o más, presentarse como un panel dentro de la cuadrícula de dos o más columnas.
