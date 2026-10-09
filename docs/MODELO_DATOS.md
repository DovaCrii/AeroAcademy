# Modelo de datos · MVP

Campos comunes en todos los modelos: `id`, `created_at`, `updated_at`.

## accounts

**Person** (extiende `AbstractUser` o perfil 1:1 con `User`)
- `login` (único, el de Tailscale), `display_name`, `avatar_url`, `role_title` (texto libre: "Modelador BIM", "Piloto RPA"…)
- `discipline` (opcional: ARQ, EST, MEP, Topografía, Captura, Documentación…)
- `is_active`
- `status`: `pending` | `approved` | `suspended`, más `approved_by` FK y `approved_at` (ver MODERACION)
- Hoja de personaje:
  - `headline`, el titular profesional;
  - `bio` (máx. 600);
  - `links` (JSON: linkedin, credly, otro);
  - `character_class` (carrera): `architect` | `bim_modeler` | `drafter` | `engineer` | `inspector` | `cartographer` | `gis` | `artificer` | `pilot` | `scanner` | `lev_lead` | `bim_coord` | `hse` (detalle en `apps/gamification/avatar/careers.py`);
  - `sheet_view`: `game` | `compact` | `pro` (vista de la hoja de personaje);
  - `selected_title` FK opcional a `gamification.Title`;
  - `avatar_config` (JSON con capas: base, tono, color, accesorio; solo accesorios desbloqueados);
  - `show_game_view` (bool).

## catalog

**Discipline**: `slug` (`arquitectura`, `civil-estructural`, `topografia`, `mecanica`, `captura-rpa`), `name`, `icon`, `order`, `default_world`
- M2M `disciplines` en: Person, Resource, LearningPath, Credential, Document, Thread, Article, Product.

**Vendor**: `slug`, `name`, `url`, `logo` (SVG opcional), `order`. Ver TAXONOMIA.
**Product**: `vendor` FK, `slug`, `name`, `disciplines` M2M, `order`.
**Platform**: `slug`, `name`, `kind` (`learning` | `certification_body` | `regulator` | `vendor`), `vendor` FK opcional, `url`, `notes`
**Skill**: `slug`, `name`, `category` (software, método, normativa…), `attribute` (`MOD` | `CAP` | `ANA` | `DOC` | `NOR` | `COL`, ver GAMIFICACION)
**Resource**: `platform` FK, `products` M2M, `title`, `url`, `kind` (`course` | `module` | `tutorial` | `exam` | `guide` | `article` | `collection` | `learning_plan`),
`proposed_by` FK opcional (curso libre promovido al catálogo),
`duration_text`, `is_official`, `is_free`, `grants_completion_certificate` (bool), `prepares_for` (texto o FK a Resource de tipo exam),
`skills` M2M, `tags` (JSON list), `description`

## paths

**LearningPath**: `slug`, `title`, `program` (ej. "CC 410 · Levantamiento Digital"), `platform` FK opcional, `description`, `is_published`,
`kind` (`structured` | `external_track`), `vendor` FK, `products` M2M, `disciplines` M2M,
`world` (`architecture` | `civil` | `survey` | `mechanical` | `aero`; ver MUNDOS), `allow_free_courses` (bool, solo `external_track`)

**ExternalCourse** (rutas `external_track`): `level` FK (capítulo), `key` (`ord-c3`), `order`, `resource` FK (curso o learning plan externo),
`reward` (`trophy` | `relic`), `is_required` (bool), `contains` (JSON: cursos que incluye un learning plan, solo informativo),
`disciplines` M2M opcional, `verify_url` (bool: la URL apunta al catálogo y falta la exacta).
- `Level.completion_rule`: `all_required` (por defecto) | `any_one` (basta un curso del capítulo; ej. OpenBuildings por disciplina).
- Se cumple cuando la persona tiene una `Credential` **verificada** con ese `resource`.
- Un curso libre aprobado y promovido crea un `Resource` nuevo (`proposed_by`) y un `ExternalCourse` al final del capítulo "Cursos libres".
**Level** — `path` FK, `code` (`n0`…), `order`, `short`, `title`, `estimated_hours`, `audience`, `goal`, `mastery_signals` (JSON list)
**LevelResource** — `level` FK, `resource` FK, `order`, `note` (descripción contextual del recurso en esa ruta)
**Milestone** — `level` FK, `key` (único por ruta, ej. `n3-t6`), `order`, `text` (admite `*término*` → `.term`),
`completed_by_credential_resource` FK opcional a Resource (si se sube un certificado de ese recurso, el hito se marca)
**QuizQuestion** — `level` FK, `key`, `order`, `question`, `options` (JSON list), `answer_index`, `explanation`
**PathExtra** — `path` FK, `kind` (`capability` | `glossary` | `team_kit` | `rollout_phase`), `order`, `data` (JSON)
  - Guarda las secciones del prototipo que no necesitan modelo propio en el MVP.
**SharedItem** — `path` FK, `key` (`kit0-1`, `ph2-3`), `text`, `group_title`, `start_week`, `end_week`

Regla de estabilidad: las `key` nunca se renumeran. Agregar hitos o preguntas siempre al final.

## progress

**MilestoneCheck** — `person` FK, `milestone` FK, `checked_at` · único (`person`, `milestone`)
**QuizAnswer** — `person` FK, `question` FK, `selected_index`, `answered_at` · único (`person`, `question`)
**PathGoal** — `person` FK, `path` FK, `certification_goal` (texto) · único (`person`, `path`)
**SharedCheck** — `item` FK a SharedItem, `checked_by` FK, `checked_at` · único (`item`)

Avance de nivel = (hitos marcados + preguntas correctas + cursos externos cumplidos) / (hitos + preguntas + cursos externos obligatorios). Se calcula, no se guarda.

## community

**Note** — `author` FK, `path` FK, `level` FK opcional, `resource` FK opcional, `type` (`works` | `fails` | `tip` | `ask` | `reply`),
`text` (máx. 1000), `parent` FK a Note opcional, `is_deleted` (borrado lógico)
- Solo el autor borra. Borrar una nota oculta también sus respuestas.

## community (foro y consultas)

**Category** — `slug`, `name`, `order`
**Thread** — `author`, `category` FK, `kind` (`discussion` | `question`), `title`, `body`, `disciplines` M2M,
`accepted_post` FK opcional (solo `question`), `is_closed`, `last_activity_at`
**Post** — `thread` FK, `author`, `body`, `is_deleted`
- Solo el autor de la consulta o un lead marcan la respuesta aceptada.

## library

**Document** — `title`, `doc_type` (`manual` | `guide` | `drawing` | `standard` | `template_rte` | `family_rfa` | `procedure` | `other`),
`disciplines` M2M, `tags` (JSON), `description`, `owner` FK, `is_restricted`
**DocumentVersion** — `document` FK, `version_label`, `file`, `file_sha256`, `notes`, `uploaded_by`, `is_current`
- Una sola versión `is_current` por documento.

## knowledge

**Article** — `title`, `body` (Markdown), `kind` (`lesson` | `procedure` | `faq`), `disciplines` M2M, `source_thread` FK opcional, `author`, `is_published`
**Improvement** — `title`, `description`, `proposed_by`, `stage` (`idea` | `plan` | `execution` | `result`), `owner` FK opcional, `outcome`

## credentials

**Credential**
- `owner` FK Person
- `title`, `issuer` (texto) y `platform` FK opcional
- `kind`: `completion` (certificado de curso) | `certification` (examen oficial) | `license` (habilitación o permiso con vencimiento, ej. credencial de piloto RPA) | `internal` (capacitación interna) | `other`
- `credential_id` (texto), `verify_url`
- `issued_on`, `expires_on` (nulo = no vence)
- `file` (privado, ver ARQUITECTURA), `file_sha256`
- `resource` FK opcional (curso o examen que acredita), `path` FK opcional
- `skills` M2M
- `status`: `pending` | `verified` | `rejected` · `reviewed_by` FK, `reviewed_at`, `review_comment`
- `visibility`: `team` (aparece en listados y matriz) | `private` (solo dueño y leads)

Propiedades calculadas: `is_expired`, `expires_soon` (≤ 60 días), `days_to_expiry`.

Reglas:
- Al editar archivo, fechas o emisor de una credencial `verified`, vuelve a `pending`.
- Al quedar `verified` con `resource` asociado, se marcan los `Milestone` con `completed_by_credential_resource` = ese recurso.

**CredentialExport** — `requested_by`, `filters` (JSON), `created_at`, `file` (ZIP temporal, se borra a las 24 h)

Campos adicionales de **Credential** para rutas externas: `course_name_free` (texto; curso libre que no está en el catálogo),
`course_url_free`, `completed_on`. Un curso libre se guarda con `resource = null` hasta que un lead lo promueve.

## team

Sin modelos propios en el MVP: vistas y servicios que agregan `progress`, `community`, `credentials` y `gamification`.
Lo único propio es **Expedition** (meta del equipo): `title`, `description`, `rule` (JSON, igual que las insignias), `target`, `starts_on`, `ends_on`, `badge` FK.

## gamification

**XPEvent**: `person` FK, `source` (texto único por persona, ej. `milestone:412`, `credential:88`, `streak:2026-W41`), `kind`, `points`, `created_at`, `revoked_at` nulo
- Único (`person`, `source`). `award()` es idempotente; `revoke()` marca `revoked_at`. El XP total suma solo los eventos no revocados.
- El nivel se calcula desde el XP total (fórmula en GAMIFICACION); no se guarda.

**Badge**: `slug`, `name`, `description`, `rarity` (`common` | `rare` | `epic` | `legendary`), `sprite` (ruta del SVG), `rule` (JSON), `is_secret`, `order`
**PersonBadge**: `person` FK, `badge` FK, `awarded_at`, `revoked_at`, `source` · único (`person`, `badge`)
**Title**: `slug`, `name`, `min_level`, `character_class` opcional, `badge` FK opcional (títulos especiales), `order`
**AvatarItem**: `slug`, `layer` (`base` | `outfit` | `accessory` | `frame`), `sprite`, `unlock_rule` (JSON; nulo = libre)

## notifications

**Notification**: `recipient` FK, `kind`, `title`, `body`, `url`, `read_at`, `created_at`
**Announcement**: `author` FK, `title`, `body` (Markdown sanitizado), `starts_at`, `expires_at`, `is_pinned`

## moderation (en `community`)

**Report**: `reporter` FK, `target_type`, `target_id`, `reason`, `status` (`open` | `resolved` | `dismissed`), `resolved_by`
**ModerationLog**: `actor` FK, `action`, `target_type`, `target_id`, `reason`, `created_at`
**Thread**: suma los campos `is_pinned` e `is_hidden`. **Post** y **Note**: suman `hidden_reason`.

## assistant

**BotUsage**: `person` FK, `day`, `count`, `tokens_in`, `tokens_out`, `last_error` · único (`person`, `day`). No guarda el texto de preguntas ni de respuestas.
**SearchIndex**: tabla virtual FTS5 (`kind`, `object_id`, `title`, `body`, `url`). Se reconstruye con `manage.py rebuild_teo_index` y se actualiza desde los services al publicar contenido.
