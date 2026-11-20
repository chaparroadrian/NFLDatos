# Implementation Plan: PocketIQ Pressure Analysis

## Overview

Implement PocketIQ incrementally in Python 3.12 and TypeScript using the approved FastAPI, pandas, React, Vite, Tailwind CSS 3 and Recharts design. The sequence establishes schemas and pure analytics first, adds lazy tracking and cached analysis, exposes the API and optional Amazon Nova functions, builds the dashboard, adds the standalone executive-summary export, and finishes with deterministic automated validation. Every step writes, modifies, or tests code and leaves its output integrated for the next step.

## Tasks

- [x] 1. Define shared backend and dashboard contracts
  - [x] 1.1 Implement the complete Pydantic request and response models in `backend/schemas.py`
    - Define strict filter inputs, analysis outputs, play detail, status, AI outputs, scouting-report sections, source labels and sample-quality models from the approved data model.
    - Reject unknown fields and invalid integer/range combinations with field-specific validation errors.
    - _Requirements: 1.13, 6.6, 10.1, 10.2, 13.10, 14.1, 14.2, 14.5, 15.1, 15.3, 15.7, 24.9, 24.10, 25.1, 26.1, 26.6, 27.1, 27.2_
  - [x] 1.2 Define dashboard API types and formatting helpers in `dashboard/src/types.ts` and `dashboard/src/format.ts`
    - Mirror the approved API schemas and implement null-safe percentage, seconds, decimal and integer formatters that never render NaN or Infinity.
    - _Requirements: 10.4, 14.2, 17.5, 17.6, 19.4, 20.5, 28.6, 28.7_

- [x] 2. Build pure analytics and the play-level PFF table
  - [x] 2.1 Implement foundational pure rules and safe serialization in `backend/analytics.py`
    - Add distance bands, field zones, sample quality, safe rates, coordinate normalization, event selection, time-to-throw, sector partitioning, contextual thresholds, forbidden-language detection and recursive JSON-safe conversion.
    - Preserve the approved constants, boundary behavior, source labels and deterministic ordering.
    - _Requirements: 3.9, 3.10, 5.1–5.7, 6.1–6.6, 7.1–7.11, 8.1–8.7, 10.3, 11.1–11.4, 11.8, 14.4, 16.3, 16.4, 22.2, 22.3_
  - [x] 2.2 Implement startup CSV loading, required-column checks and validation logging in `backend/analytics.py`
    - Read only the four approved small CSV files, fail clearly for missing files or columns, preserve the first duplicate play, join only on approved IDs, and emit at most one credential-free warning per check and file.
    - Keep every access to `data/` read-only and avoid all derived-file persistence.
    - _Requirements: 1.14, 2.1–2.3, 2.10–2.13, 3.1–3.3, 3.7, 3.8, 3.11, 23.4_
  - [x] 2.3 Construct the one-row-per-play analytical table and PFF aggregates in `backend/analytics.py`
    - Implement role validation, rusher/blocker/chip logic, pressure and offensive-charge indicators, null propagation, field context and initial pending tracking columns.
    - Preserve plays without PFF rows and compute both independent sack definitions without conflating them.
    - _Requirements: 3.2, 3.3, 4.1–4.16, 5.1–5.7, 6.1–6.3_

- [x] 3. Add incremental tracking, spatial metrics and diagnoses
  - [x] 3.1 Implement per-game tracking ingestion and integrity checks in `backend/analytics.py`
    - Load only the approved nine columns for games where the selected opponent defends, keep at most one raw tracking DataFrame alive, validate teams, ball uniqueness and play direction, and safely skip unreadable game files.
    - _Requirements: 2.4–2.6, 2.11, 2.12, 2.14, 3.4, 3.5, 3.7, 3.8, 8.3, 8.5_
  - [x] 3.2 Implement event windows, threat metrics, sectors and clipped trajectories in `backend/analytics.py`
    - Select manual/automatic snap and pass frames, derive evaluation windows, time-to-throw, nearest-rusher threat, minimum distance, tie-breaking, normalized sector and ordered events.
    - Retain only immutable clipped trajectories and per-play aggregates after each file is released.
    - _Requirements: 2.6, 3.6, 7.1–7.11, 8.1–8.7, 9.1–9.8, 11.1–11.8, 15.2, 15.5, 15.6_
  - [x] 3.3 Implement static and contextual protection diagnoses in `backend/analytics.py`
    - Add ordered PFF and inferred diagnoses, free-rusher detection, double team, chip/help, three-frame stunt detection, QB movement and percentile-based prolonged-pressure logic.
    - Guarantee at least one nonduplicated diagnosis per play and use only cautious, source-labelled language.
    - _Requirements: 12.1–12.13, 16.3, 16.4_
  - [x] 3.4 Implement atomic per-opponent tracking cache and bounded result cache in `backend/analytics.py`
    - Add per-opponent synchronization, atomic commit after complete processing, cleanup after failure, in-memory-only storage, canonical filter keys and deterministic cache hits.
    - Expose tracking readiness/in-progress state without rereading cached tracking.
    - _Requirements: 2.7–2.10, 2.15, 12.13, 14.6, 14.9_

- [x] 4. Build analysis results, detail views and deterministic reports
  - [x] 4.1 Implement conjunctive filtering and complete analysis response assembly in `backend/analytics.py`
    - Apply every filter together, make exact distance override distance band, calculate sample metadata, summary rates, five sectors, all distributions and the required empty result.
    - Include skipped tracking games, subset sample sizes, sources, active filters and null-safe values.
    - _Requirements: 5.7, 6.4, 6.5, 10.1–10.3, 10.9, 13.1, 13.8, 13.9, 14.2–14.4, 14.8, 18.1–18.6_
  - [x] 4.2 Implement protection-response comparisons in `backend/analytics.py`
    - Produce all six dimensions, preserve multiple block-type membership, calculate alternative-level outcomes and quality, and exclude nulls only from their own dimension.
    - _Requirements: 19.1–19.6_
  - [x] 4.3 Implement deterministic representative-play selection and play detail in `backend/analytics.py`
    - Select up to one play in each approved category with stable tie-breaking and confidence, then expose context, players, sources, diagnoses, trajectories and events for valid plays.
    - Return a distinguishable missing result and retain available context when snap or tracking is absent.
    - _Requirements: 15.1–15.6, 15.8, 20.1–20.7_
  - [x] 4.4 Implement the deterministic executive summary and six-section scouting report in `backend/analytics.py`
    - Generate stable Spanish text, small/empty-sample variants, cautious association language, validated citations and all six report sections without external services.
    - _Requirements: 10.6, 16.1–16.8, 20.3, 27.2–27.6, 27.8, 27.10, 27.11, 27.13, 27.14_

- [ ] 5. Expose the FastAPI application and same-origin dashboard
  - [x] 5.1 Implement lifecycle, routes and error handling in `backend/main.py`
    - Place and execute the exact manual `cargar_env()` block from `.kiro/steering/rules.md` before importing `backend.ai`; do not add `python-dotenv` or inspect credential variables in backend code.
    - Initialize the engine in lifespan and expose exact health, filters, analysis, play-detail and opponent-status behavior with safe 404, 422 and 500 JSON responses.
    - _Requirements: 1.1–1.3, 1.6, 2.3, 2.13–2.15, 6.6, 13.1, 13.9–13.11, 14.1–14.10, 15.1, 15.4, 15.7, 23.7, 24.4, 24.5, 24.15_
  - [-] 5.2 Implement safe static build serving and API fallback behavior in `backend/main.py`
    - Serve existing files and SPA fallback from `dashboard/dist` without requiring the directory at startup, block path traversal, and ensure unknown `/api/` routes always return JSON 404.
    - _Requirements: 1.4–1.6, 21.8, 23.7_

- [ ] 6. Integrate Amazon Nova with deterministic fallback
  - [x] 6.1 Implement lazy Bedrock Converse infrastructure and AI context construction in `backend/ai.py`
    - Use only `AWS_REGION` with default `us-east-1`, model default `us.amazon.nova-pro-v1:0`, `boto3.client("bedrock-runtime", region_name=region, config=...)`, bounded timeouts and a replaceable client factory.
    - Never read or verify credential variables, pass credentials to boto3, embed environment values, send raw tracking, create a client at import, or call another AWS service.
    - _Requirements: 24.1–24.6, 24.8, 24.12–24.15, 25.3, 26.4_
  - [-] 6.2 Implement trends and diagnosis validation flows in `backend/ai.py`
    - Parse structured Converse output, verify cited facts against flattened analytics context, correct sources, move unsupported diagnosis facts to hypotheses, mark cautious-language issues and return deterministic empty/failure responses.
    - _Requirements: 24.9–24.11, 25.3–25.12, 26.3–26.13_
  - [~] 6.3 Implement Nova scouting-report validation and fallback in `backend/ai.py`
    - Validate alternative support, sample quality and cited plays; remove unsupported recommendations; merge comparable plays deterministically; and return the analytics-generated report whenever Nova is unavailable or n is zero.
    - _Requirements: 24.9, 24.10, 27.1–27.14_
  - [~] 6.4 Wire the three AI POST endpoints into `backend/main.py`
    - Reuse the strict schemas and analytics engine, preserve non-AI behavior during every AI failure, and keep all generated AI text isolated under `/api/ai/`.
    - _Requirements: 16.9, 24.7, 24.9–24.11, 25.1, 25.2, 26.1–26.3, 27.1, 27.12_

- [x] 7. Build dashboard foundations and core analysis panels
  - [x] 7.1 Configure Vite, Tailwind CSS 3 and global responsive styles
    - Preserve `base: './'`, add only the approved development proxy, use no external assets or new dependencies, and establish the approved dark analysis-room theme, contrast and print styles.
    - _Requirements: 1.8–1.11, 21.1–21.9, 23.3_
  - [x] 7.2 Implement the relative-path API client in `dashboard/src/api.ts`
    - Add filter, analysis, status, play-detail and AI calls using only `api/...` URLs, with distinct 422 and general failure handling.
    - _Requirements: 1.7, 13.11, 14.10, 20.8, 20.9, 28.2, 28.8, 28.9_
  - [x] 7.3 Implement shared sample, source, warning, loading, empty and error components
    - Display text in addition to color and preserve explicit null, small-sample, unverified and language-warning states.
    - _Requirements: 9.5, 10.4, 10.5, 10.10, 12.11, 12.12, 14.7, 17.6, 21.4–21.6, 28.13_
  - [x] 7.4 Implement header and responsive filter controls
    - Add the exact header copy, all pre-snap and post-snap filters, recommended distance band, exact-distance validation, mobile drawer and the one-request analysis action without clearing state on error.
    - _Requirements: 6.7, 10.7, 10.8, 13.2–13.8, 17.1, 21.6, 21.7_
  - [x] 7.5 Implement executive summary, metric cards and five-sector SVG pressure map
    - Show all required labels, sources, samples, discrepancy details, formatting, geometric disclaimer, low-intensity empty sectors and loading/error/empty states.
    - _Requirements: 4.7, 4.13, 9.5, 10.4–10.10, 11.7, 17.2–17.11_

- [x] 8. Add advanced analysis and play-review panels
  - [x] 8.1 Implement defensive trends charts and diagnosis table
    - Render Recharts distributions with visible values, all seven diagnoses, source labels, multiple-membership caveats and null threat-time handling.
    - _Requirements: 12.5, 12.11, 12.12, 18.1–18.8, 21.3, 21.4_
  - [x] 8.2 Implement sortable protection-response tables
    - Render six dimensions, initial and interactive sorting with nulls last, block-type caveat, outcome metrics and non-categorical warnings below n 30.
    - _Requirements: 10.4, 10.5, 19.3, 19.7–19.9_
  - [x] 8.3 Implement representative plays and tracking detail modal
    - Render all five category slots and required fields, request details by relative URL, and draw frame-controlled normalized trajectories with distinct non-color shapes for rushers, blockers, chips, QB and ball.
    - _Requirements: 15.1–15.8, 20.5–20.10, 21.3, 21.4_
  - [x] 8.4 Wire all non-AI panels and state transitions in `dashboard/src/App.tsx`
    - Coordinate initial filter loading, user-triggered analysis, active filters, loading, errors, empty data, filter expansion and play selection while preserving user choices.
    - _Requirements: 10.7, 10.8, 13.3, 13.8, 13.11, 14.7, 14.10, 17.11, 18.7, 20.9_

- [ ] 9. Add the AI dashboard panel
  - [~] 9.1 Implement independent AI action state and trends/diagnosis views
    - Provide the three controls, independent loading/results, facts and hypotheses, source/sample labels, warnings, cited-play detail links, retries and non-destructive failure behavior.
    - _Requirements: 25.10, 28.1–28.9, 28.13, 28.14_
  - [~] 9.2 Implement the scouting report view and browser actions
    - Render all six ordered sections, distinguish Amazon Nova from deterministic fallback, copy with failure notice, and print through native browser APIs.
    - _Requirements: 27.2, 28.5, 28.10–28.14_
  - [~] 9.3 Integrate the AI panel into `dashboard/src/App.tsx`
    - Pass current filters and play-detail callbacks without replacing or hiding the deterministic analysis when AI is unavailable.
    - _Requirements: 16.9, 23.8, 24.11, 28.2–28.10, 28.14_

- [ ] 10. Add standalone export and verified project guidance
  - [~] 10.1 Implement `backend/export_executive_summary.py`
    - Build the root `resumen_ejecutivo.html` from the real analytics engine and the same AI/scouting-report logic, choosing a deterministic real opponent by default and accepting explicit filters without hard-coded findings.
    - Emit a self-contained HTML/CSS/JavaScript document with no external dependencies, no embedded credentials or environment values, and no writes under `data/`; if Nova is unavailable, include the deterministic report and clear fallback label.
    - _Requirements: 1.14, 2.1, 2.2, 2.10, 10.1–10.6, 16.1–16.6, 24.4, 24.6, 24.9, 24.11–24.14, 27.2–27.8_
  - [ ]* 10.2 Add automated export tests
    - Verify deterministic opponent selection, engine-derived values, fallback output, self-contained markup, root output path, absence of credential values and unchanged `data/` inventory.
    - _Requirements: 1.14, 2.2, 16.2, 22.3, 22.12, 23.4, 24.6, 24.9_
  - [~] 10.3 Update `README.md` with verified real findings and execution instructions
    - Run the completed analytics engine against real data to derive and cite reproducible findings, clearly label their filters, sample sizes and sources, and avoid unsupported causal claims.
    - Document environment check, tests, dashboard build, Uvicorn execution and executive-summary export; describe `.env`/AWS role setup without credential values, without credential verification code and without adding dependencies.
    - _Requirements: 10.1–10.6, 16.3–16.5, 23.1–23.3, 23.8, 23.9, 24.2–24.6_

- [ ] 11. Add deterministic fixtures and focused example tests
  - [~] 11.1 Implement in-memory analytics and API fixtures in `tests/conftest.py`
    - Add DataFrame factories, spy tracking loaders with concurrency counters, engine/client fixtures and a configurable fake Converse client; unit/property tests must not open real tracking files.
    - _Requirements: 2.4, 2.9, 22.4, 22.11, 22.12_
  - [ ]* 11.2 Add pure-rule and tracking example tests in `tests/test_rules.py`
    - Cover all specified boundaries for bands, zones, quality, events, normalization, orientation, blitz threshold, missing values, threat distance, stunt frames and diagnoses.
    - _Requirements: 7.1–7.11, 8.1–8.7, 9.1–9.8, 11.5, 11.6, 12.1–12.10, 22.2, 22.9, 22.10_
  - [ ]* 11.3 Add API, routing, cache and error tests in `tests/test_api.py`
    - Exercise exact health output, filters, complete/empty analysis, safe JSON, play details, unknown API routes, missing dist, skipped tracking, concurrent same-opponent requests and clean cache failures through httpx.
    - _Requirements: 1.2, 1.4–1.6, 2.8, 2.9, 2.14, 2.15, 14.2–14.9, 15.4–15.8, 22.1, 22.3_
  - [ ]* 11.4 Add AI unit and endpoint tests in `tests/test_ai.py`
    - Verify lazy Converse calls, exact region/model defaults, client arguments, structured validation, timeouts, n-zero bypass, deterministic fallback, factual grounding, warning markers and secret-value non-disclosure using only fake clients.
    - _Requirements: 22.12, 24.2–24.15, 25.1–25.12, 26.1–26.13, 27.1–27.14_
  - [ ]* 11.5 Add static contract tests
    - Check dependency versions, `.env` ignore, exact `cargar_env()` placement, absence of backend credential-variable references, relative dashboard URLs, Vite base/proxy, approved Bedrock service/model literals and no external frontend resources.
    - _Requirements: 1.7–1.11, 21.8, 21.9, 23.9, 24.1–24.7, 24.13, 24.15_

- [ ] 12. Encode analytics correctness properties
  - [ ]* 12.1 Write property test for distance-band partition
    - **Property 1: Partición de la banda de distancia**
    - **Validates: Requirements 6.1, 6.2, 6.3, 22.2, 22.5**
  - [ ]* 12.2 Write property test for end-zone distance and field-zone partition
    - **Property 2: Distancia a la zona de anotación y partición de la zona del campo**
    - **Validates: Requirements 5.1–5.6, 22.2, 22.6**
  - [ ]* 12.3 Write property test for sample-quality partition
    - **Property 3: Partición de la calidad de muestra**
    - **Validates: Requirements 10.3, 22.2**
  - [ ]* 12.4 Write property test for sector partition
    - **Property 4: Partición de Sectores**
    - **Validates: Requirements 11.1, 11.3, 11.8**
  - [ ]* 12.5 Write property test for coordinate normalization and involution
    - **Property 5: Normalización y su involución**
    - **Validates: Requirements 8.1, 8.2, 8.4, 8.6, 22.10**
  - [ ]* 12.6 Write property test for direction-mirror invariance
    - **Property 6: Invariancia ante el espejo de dirección**
    - **Validates: Requirements 8.7, 11.5**
  - [ ]* 12.7 Write property test for snap/pass event selection
    - **Property 7: Selección de eventos de snap y pase**
    - **Validates: Requirements 7.1–7.6, 7.11, 22.9**
  - [ ]* 12.8 Write property test for exact time-to-throw and null reasons
    - **Property 8: timeToThrow exacto y nulos con motivo**
    - **Validates: Requirements 3.6, 7.7–7.10, 22.9**
  - [ ]* 12.9 Write property test for exhaustive proximity-threat matching
    - **Property 9: Amenaza por proximidad coincide con la búsqueda exhaustiva**
    - **Validates: Requirements 9.1–9.3, 9.7, 9.8, 11.1, 11.2, 11.4**
  - [ ]* 12.10 Write property test for PFF aggregate reference equivalence
    - **Property 10: Agregados PFF coinciden con el modelo de referencia**
    - **Validates: Requirements 3.3, 4.3–4.10, 4.14, 4.16, 22.10**
  - [ ]* 12.11 Write property test for diagnosis structure and rules
    - **Property 11: Estructura y reglas de los Diagnosticos**
    - **Validates: Requirements 12.1–12.4, 12.6, 12.9, 12.10**
  - [ ]* 12.12 Write property test for one analytical row per play
    - **Property 12: Una fila por jugada**
    - **Validates: Requirements 3.1, 4.1**
  - [ ]* 12.13 Write property test for conjunctive filters
    - **Property 13: Los filtros se aplican de forma conjunta**
    - **Validates: Requirements 5.7, 6.4, 6.5, 10.1, 13.8, 13.9, 23.6**
  - [ ]* 12.14 Write property test for monotonic sample size under added filters
    - **Property 14: Agregar un filtro nunca aumenta n**
    - **Validates: Requirements 13.8, 22.8**
  - [ ]* 12.15 Write property test for bounded rates and nonnegative counts
    - **Property 15: Tasas en [0, 1] y conteos enteros no negativos**
    - **Validates: Requirements 3.9, 3.10, 4.11, 14.2, 18.1, 18.2, 19.4, 22.7**
  - [ ]* 12.16 Write property test for complete analysis-response structure
    - **Property 16: Estructura completa de la respuesta de análisis**
    - **Validates: Requirements 10.2, 10.9, 14.2, 14.3, 14.8, 22.1**
  - [ ]* 12.17 Write property test for finite JSON serialization
    - **Property 17: JSON sin NaN ni infinitos**
    - **Validates: Requirements 14.4, 15.8, 22.3**
  - [ ]* 12.18 Write property test for determinism and cache reuse
    - **Property 18: Determinismo y caché**
    - **Validates: Requirements 2.8, 2.10, 12.13, 14.6, 16.2, 20.3, 27.10**
  - [ ]* 12.19 Write property test for independent sack-rate discrepancy
    - **Property 19: Discrepancia entre las dos tasas de sack**
    - **Validates: Requirements 4.11, 4.12**
  - [ ]* 12.20 Write property test for protection-response counts
    - **Property 20: Conteos de las respuestas de protección**
    - **Validates: Requirements 19.1–19.6**
  - [ ]* 12.21 Write property test for valid representative plays
    - **Property 21: Jugadas representativas válidas**
    - **Validates: Requirements 20.1–20.4, 20.7**
  - [ ]* 12.22 Write property test for summary shape and cautious language
    - **Property 22: Estructura y lenguaje del resumen automático**
    - **Validates: Requirements 10.6, 16.1, 16.3, 16.4, 16.6, 16.8**
  - [ ]* 12.23 Write property test for invalid input rejection
    - **Property 23: Entradas inválidas producen 422**
    - **Validates: Requirements 6.6, 13.10, 14.1, 14.5, 25.1, 25.2, 26.1, 26.2, 27.12**
  - [ ]* 12.24 Write property test for unknown routes and plays
    - **Property 24: Rutas y jugadas inexistentes**
    - **Validates: Requirements 1.5, 15.4, 26.3**
  - [ ]* 12.25 Write property test for opponent-scoped single-pass tracking
    - **Property 25: Solo se lee el tracking del Rival, un archivo a la vez**
    - **Validates: Requirements 2.4, 2.9**
  - [ ]* 12.26 Write property test for detail trajectories and events
    - **Property 26: Trayectorias y eventos del detalle**
    - **Validates: Requirements 2.6, 15.2, 15.6**

- [ ] 13. Encode AI and API correctness properties
  - [ ]* 13.1 Write property test for grounded AI facts
    - **Property 27: Ningún Hecho sobrevive si no coincide con el Contexto_IA**
    - **Validates: Requirements 25.5, 25.6, 26.7–26.10**
  - [ ]* 13.2 Write property test for supported recommendations
    - **Property 28: Ninguna recomendación sin jugada válida ni respaldo exacto**
    - **Validates: Requirements 27.3–27.5, 27.13**
  - [ ]* 13.3 Write property test for fixed scouting-report shape
    - **Property 29: Forma fija del Reporte_Scouting**
    - **Validates: Requirements 27.2, 27.6, 27.8, 27.11, 27.14**
  - [ ]* 13.4 Write property test for AI failure isolation
    - **Property 30: Los fallos de IA no alteran el análisis**
    - **Validates: Requirements 16.5, 24.9, 24.11, 25.12, 26.6, 26.13, 27.8**
  - [ ]* 13.5 Write property test for credential non-disclosure
    - **Property 31: Las credenciales nunca aparecen en salidas**
    - **Validates: Requirements 22.12, 24.6, 24.12**
  - [ ]* 13.6 Write property test for bounded AI timeout parsing
    - **Property 32: Tiempo límite de IA acotado**
    - **Validates: Requirements 24.8**
  - [ ]* 13.7 Write property test for AI-context consistency
    - **Property 33: El Contexto_IA es consistente con el análisis**
    - **Validates: Requirements 24.14, 25.4, 26.4**
  - [ ]* 13.8 Write property test for language-warning detection
    - **Property 34: La marca de lenguaje coincide con el detector**
    - **Validates: Requirements 25.8, 26.11, 27.7**
  - [ ]* 13.9 Write property test for filter-list uniqueness and ordering
    - **Property 35: Listas de `/api/filters`**
    - **Validates: Requirements 13.1**

- [ ] 14. Add real-data and final automated validation
  - [ ]* 14.1 Add optional real-data smoke tests in `tests/test_smoke_real_data.py`
    - Verify a real opponent’s n, sub-60-second first analysis, sector orientation and a before/after inventory of every `data/` file including name, size and modification timestamp.
    - _Requirements: 1.14, 2.2, 11.5, 11.6, 23.4–23.6_
  - [ ]* 14.2 Run the complete Python test suite with `.venv/bin/pytest`
    - Execute all non-network tests from the repository root and fix code or tests until there are no failures or collection errors.
    - _Requirements: 22.1–22.12, 23.2_
  - [ ]* 14.3 Build the dashboard with `npm run build`
    - Run the command in `dashboard/`, fix TypeScript/Vite failures, and verify `dashboard/dist/index.html` references only relative bundled assets.
    - _Requirements: 1.10, 21.8, 21.9, 23.3_
  - [ ]* 14.4 Run environment verification with `sh .hackathon/setup.sh --check`
    - Fix only implementation or manifest issues allowed by the approved stack until the check exits successfully without dependency/version errors.
    - _Requirements: 1.11, 23.1_
  - [ ]* 14.5 Run same-process endpoint smoke tests against the built dashboard
    - Start Uvicorn only for the bounded smoke-test duration, verify exact `/health`, filters, analysis, play detail, AI fallback and dashboard asset responses, then stop it cleanly.
    - _Requirements: 1.2–1.6, 14.2–14.4, 15.1–15.8, 23.7, 23.8, 24.11_
  - [ ]* 14.6 Verify final data immutability and credential hygiene
    - Compare the saved before/after `data/` inventory, require no added/deleted/changed entries, confirm `.env` remains ignored and scan versioned files and generated `resumen_ejecutivo.html` for credential values without printing them.
    - _Requirements: 1.14, 2.2, 23.4, 23.9, 24.6_

- [~] 15. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test tasks and may be skipped for a faster MVP; all unstarred implementation tasks are required.
- Property cases use pytest parametrization or `random.Random` with fixed seeds. They must not add Hypothesis or any dependency.
- Backend code must not mention or inspect credential-variable names. Tests may inject fake values only to verify non-disclosure.
- `backend/main.py` must contain the exact `cargar_env()` implementation from `.kiro/steering/rules.md`; no `python-dotenv` dependency is permitted.
- Amazon Nova integration belongs only in `backend/ai.py`, uses the default model `us.amazon.nova-pro-v1:0`, reads only `AWS_REGION` for region selection, and creates only a region-configured Bedrock Runtime client. Credentials remain externally supplied by `.env` or the AWS role and are never persisted.
- The standalone export is an explicit offline deliverable. Runtime API and dashboard behavior remain ephemeral and do not depend on the generated HTML file.
- No task writes under `data/`, adds dependencies, deploys infrastructure, or implements a service outside the approved stack.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "7.1"] },
    { "id": 2, "tasks": ["2.2", "7.2"] },
    { "id": 3, "tasks": ["2.3", "7.3"] },
    { "id": 4, "tasks": ["3.1", "7.4"] },
    { "id": 5, "tasks": ["3.2", "7.5"] },
    { "id": 6, "tasks": ["3.3", "8.1"] },
    { "id": 7, "tasks": ["3.4", "8.2"] },
    { "id": 8, "tasks": ["4.1", "8.3"] },
    { "id": 9, "tasks": ["4.2"] },
    { "id": 10, "tasks": ["4.3"] },
    { "id": 11, "tasks": ["4.4", "8.4"] },
    { "id": 12, "tasks": ["5.1", "6.1"] },
    { "id": 13, "tasks": ["5.2", "6.2"] },
    { "id": 14, "tasks": ["6.3", "9.1"] },
    { "id": 15, "tasks": ["6.4", "9.2"] },
    { "id": 16, "tasks": ["9.3", "10.1", "11.1"] },
    { "id": 17, "tasks": ["10.2", "11.2", "11.4"] },
    { "id": 18, "tasks": ["10.3", "11.3", "12.1", "13.1"] },
    { "id": 19, "tasks": ["11.5", "12.2", "13.2"] },
    { "id": 20, "tasks": ["12.3", "13.3"] },
    { "id": 21, "tasks": ["12.4", "13.4"] },
    { "id": 22, "tasks": ["12.5", "13.5"] },
    { "id": 23, "tasks": ["12.6", "13.6"] },
    { "id": 24, "tasks": ["12.7", "13.7"] },
    { "id": 25, "tasks": ["12.8", "13.8"] },
    { "id": 26, "tasks": ["12.9", "13.9"] },
    { "id": 27, "tasks": ["12.10"] },
    { "id": 28, "tasks": ["12.11"] },
    { "id": 29, "tasks": ["12.12"] },
    { "id": 30, "tasks": ["12.13"] },
    { "id": 31, "tasks": ["12.14"] },
    { "id": 32, "tasks": ["12.15"] },
    { "id": 33, "tasks": ["12.16"] },
    { "id": 34, "tasks": ["12.17"] },
    { "id": 35, "tasks": ["12.18"] },
    { "id": 36, "tasks": ["12.19"] },
    { "id": 37, "tasks": ["12.20"] },
    { "id": 38, "tasks": ["12.21"] },
    { "id": 39, "tasks": ["12.22"] },
    { "id": 40, "tasks": ["12.23"] },
    { "id": 41, "tasks": ["12.24"] },
    { "id": 42, "tasks": ["12.25"] },
    { "id": 43, "tasks": ["12.26"] },
    { "id": 44, "tasks": ["14.1"] },
    { "id": 45, "tasks": ["14.2"] },
    { "id": 46, "tasks": ["14.3"] },
    { "id": 47, "tasks": ["14.4"] },
    { "id": 48, "tasks": ["14.5"] },
    { "id": 49, "tasks": ["14.6"] }
  ]
}
```
