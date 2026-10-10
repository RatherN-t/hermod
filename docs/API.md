# Hermod API (for the frontend)

The backend serves a JSON API for the doctor dashboard and the prescription form. Everything
the dashboard needs is here: patients, reminders (prescribed medications), the dose
timeline, adherence numbers, flags, the patient's conversation with Hermod, and the agent
trace behind every reply.

- **Base URL (local):** `http://localhost:8000`
- **Interactive docs:** `http://localhost:8000/docs` lists every endpoint with its schema,
  and lets you send requests from the browser. Raw spec: `/openapi.json` (you can generate
  TypeScript types from it, e.g. `npx openapi-typescript http://localhost:8000/openapi.json -o src/api.d.ts`).
- **CORS:** `http://localhost:5173` (Vite) is allowed. Other origins go in `CORS_ORIGINS` in `.env`.
- **Auth:** none by default. If `API_KEY` is set in the backend `.env`, send header
  `X-API-Key: <key>` on every `/api` request (401 otherwise).

## Conventions

- JSON keys are **camelCase**. Requests accept camelCase (snake_case also works).
- Datetimes are ISO 8601 in UTC with `Z`, e.g. `"2026-10-10T21:00:00Z"`. Show them in the
  clinic's timezone (Australia/Sydney).
- Dates are `"YYYY-MM-DD"`. Times of day are 24-hour `"HH:MM"` in clinic-local time.
- IDs are integers. A **reminder id is a medication id**: one reminder = one medication on its
  own course.
- Errors: `404 {"detail": "Patient 9 not found"}`, `409` for conflicts (duplicate phone,
  patient not linked), `422` for validation, with `detail` as a string or a list like
  `[{"loc": ["body", "timesOfDay"], "msg": "Value error, '8am' is not HH:MM (24-hour)"}]`.
- There's no push channel; poll (e.g. every 10–30s) for new messages and flags.

## Endpoints

| Method & path | What it's for |
| --- | --- |
| `GET /api/dashboard` | Clinic overview: counts, `needsAttention` patients, recent flags and messages |
| `GET /api/patients?q=` | Patient list with adherence, open flag counts and next dose (`q` = name contains) |
| `POST /api/patients` | Create a patient → full detail incl. their Telegram start link |
| `GET /api/patients/{id}` | Everything about one patient: profile, link, adherence, flags, reminders |
| `PATCH /api/patients/{id}` | Edit name, doctor, DOB, language, next appointment, notes |
| `DELETE /api/patients/{id}` | **Permanent.** Deletes the patient and all their reminders, doses, messages, traces and flags → `204`. Confirm with the user first |
| `GET /api/patients/{id}/link` | `{linked, linkCode, telegramLink}`; show as a link or QR code |
| `POST /api/patients/{id}/link/reset` | New link, unlinks the current chat (if the link leaked) |
| `GET /api/patients/{id}/reminders` | The patient's reminders (all statuses) |
| `POST /api/patients/{id}/reminders` | Prescribe: creates the course and schedules every dose |
| `GET /api/reminders/{id}` | One reminder |
| `PATCH /api/reminders/{id}` | Pause/resume, change times, course length, dose, instructions, message, alerting |
| `POST /api/reminders/{id}/end` | Stop the course now (doctor discontinued it); history kept |
| `POST /api/reminders/{id}/checkin` | Send the check-in right now (handy in demos) |
| `GET /api/patients/{id}/doses?from=&to=&status=&reminderId=` | Dose timeline, oldest first, includes future doses |
| `GET /api/patients/{id}/adherence?days=14` | Overall + per-medication adherence and a per-day series for charts |
| `GET /api/patients/{id}/messages?limit=100` | The conversation, oldest first, with `traceIds` |
| `GET /api/patients/{id}/traces?limit=50` | The patient's LLM calls, newest first |
| `GET /api/traces/{id}` | One LLM call in full: prompt, output, tool calls, latency, error |
| `GET /api/flags?status=open&severity=&patientId=` | Flags across patients, newest first (`status`: open/resolved/all) |
| `GET /api/patients/{id}/flags?status=all` | One patient's flags |
| `PATCH /api/flags/{id}` | `{"resolved": true}` to resolve (or `false` to reopen) |
| `GET /health` | `{"status": "ok"}` |

## Your form types → the API

`ReminderDraft` (in `frontend/src/features/med-reminders/types.ts`) maps onto
`POST /api/patients/{id}/reminders`:

| `ReminderDraft` | Request field | Notes |
| --- | --- | --- |
| `name` | `name` | Required |
| | `dose` | e.g. `"1 capsule"` (default `"1 dose"`) |
| | `instructions` | e.g. `"with food"` |
| `timesOfDay` | `timesOfDay` | Array of `"HH:MM"`, 1–8 items; sorted and de-duplicated |
| `durationKind` | `durationKind` | `"days"` \| `"date"` \| `"appointment"` |
| `durationDays` | `durationDays` | 1–180, for `"days"` |
| `untilDate` | `untilDate` | Last day, for `"date"` |
| | `startDate` | Optional, today or later; default now |
| `customMessage` | `customMessage` | `null` = standard message. May use `{name}`, `{medication}`, `{dose}`, `{time}` |
| `alertOnMissed` | `alertOnMissed` | Off = no "missed doses" flags for this medication |
| `waPhone` | (on the patient) `phone` | The patient's id/contact; Telegram links by `link`, not phone |
| `language` | (on the patient) `language` | `"en"`/`"es"`; stored only, Hermod replies in English |
| `consent`, `phoneEdited` | not stored | Keep client-side |

`durationKind: "appointment"` ends the course at the patient's `nextAppointmentAt`, so set
that on the patient first (422 otherwise).

**Editing a reminder** (`PATCH /api/reminders/{id}`, send only what changed): `status`
(`"active"`/`"paused"`), `timesOfDay`, `customMessage` (`""` = standard message),
`alertOnMissed`, `dose`, `instructions`, `maxDailyDoses`, and the course length with the same
fields as create: `durationKind`, `durationDays`, `untilDate`. Course length counts from the
course's original `startDate`, e.g. `{"durationDays": 10}` on a course that started 3 days ago
leaves 7 more days. Leaving out `durationKind` keeps the current kind;
`{"durationKind": "appointment"}` ends at the patient's current `nextAppointmentAt`. A length
change moves `endDate`, recomputes `totalDoses`, and replaces the upcoming doses (past doses and
any already asked about are kept), the same way pause/resume and new times do. 422 if the
new end would be in the past (use `POST /api/reminders/{id}/end` to stop now), and the same
422s as create for a missing `durationDays`/`untilDate` or no future appointment. Changing the
length of an ended course reopens it if the new end is in the future.

`ActiveReminder` ↔ the `Reminder` response: `id, name, timesOfDay, durationKind,
durationDays, startDate, endDate, status, customMessage, alertOnMissed, dosesSent,
dosesConfirmed, totalDoses` all exist with those names. `status` is
`"active" | "paused" | "scheduled" | "ended"` (your type has the first two). Extra:
`dose, instructions, maxDailyDoses, nextDoseAt, prescriptionId, patientId`. `untilDate` isn't
returned; use `endDate`. In responses, `startDate` and `endDate` are UTC datetimes (e.g.
`"2026-10-08T12:59:59Z"` is the end of Oct 8 in Sydney), not `"YYYY-MM-DD"`; convert to the
clinic's timezone before showing a calendar date. `name` can't be changed with `PATCH`; add a
new reminder instead.

## Typical flows

**Add a patient and prescribe**

```http
POST /api/patients
{"name": "Sam Taylor", "phone": "61400000000", "doctorName": "Dr Lee", "dateOfBirth": "1990-05-02"}
→ 201 { "id": 1, ..., "link": {"linked": false, "linkCode": "RWTg1riNyaBg",
        "telegramLink": "https://t.me/Hermod_demo_yash_bot?start=RWTg1riNyaBg"} }

POST /api/patients/1/reminders
{"name": "Amoxicillin 500mg", "dose": "1 capsule", "timesOfDay": ["08:00", "14:00", "20:00"],
 "durationKind": "days", "durationDays": 7, "instructions": "Finish the full course"}
→ 201 { "id": 1, "status": "active", "totalDoses": 18, "nextDoseAt": "2026-10-10T21:00:00Z", ... }
```

Show `link.telegramLink` (or a QR code of it) for the patient to open. `link.linked` turns
`true` once they tap **Start** in Telegram. `telegramLink` is `null` if the backend has no
bot token.

**Doctor dashboard:** `GET /api/dashboard` for the overview, then per patient
`GET /api/patients/{id}`, `/adherence` for charts, `/doses` for the timeline, `/flags`, and
`/messages` for the chat.

**"Why did Hermod say that?"** Each message has `traceIds`. A reply (`direction: "out"`)
carries the ids of the LLM calls that produced it (`inReplyToId` is the patient message it
answers). `GET /api/traces/{id}` returns the full prompt and the tool calls, e.g.
`{"name": "log_dose", "arguments": {"status": "taken", "dose_id": 3}}`. Emergency
escalations and scheduled check-ins have no traces because they don't use the LLM.

## Response shapes (abridged; `/docs` has the full schemas)

`GET /api/patients/{id}`:

```json
{
  "id": 1, "name": "Sam Taylor", "phone": "61400000000", "doctorName": "Dr Lee",
  "language": "en", "isSynthetic": true, "telegramLinked": false,
  "dateOfBirth": "1990-05-02", "notes": "", "nextAppointmentAt": null,
  "lastMessageAt": "2026-10-10T10:00:20Z", "createdAt": "2026-10-10T10:00:20Z",
  "activeReminders": 1,
  "adherence": {"taken": 4, "late": 1, "missed": 1, "unknown": 0, "extra": 0, "pending": 1,
                "adherencePct": 83},
  "openFlags": {"urgent": 0, "warning": 1, "info": 0, "total": 1},
  "nextDose": {"doseId": 7, "reminderId": 1, "medication": "Amoxicillin 500mg",
               "scheduledFor": "2026-10-10T21:00:00Z"},
  "link": {"linked": false, "linkCode": "RWTg1riNyaBg", "telegramLink": "https://t.me/..."},
  "reminders": [ /* Reminder objects */ ]
}
```

`adherencePct` = (taken + late) / doses that were due (taken, late, missed, unknown). It's
`null` until a dose is due. `unknown` = no reply within 6 hours.

`GET /api/patients/{id}/doses` item:

```json
{"id": 1, "reminderId": 1, "medication": "Amoxicillin 500mg",
 "scheduledFor": "2026-10-10T21:00:00Z", "status": "pending",
 "checkinSentAt": null, "reportedAt": null, "note": ""}
```

`status` is one of `pending, taken, late, missed, extra, unknown`. An `extra` dose is one the patient
reported beyond the schedule: `scheduledFor` is when they reported it, and `note` holds their
words, e.g. `"Reported overdose: \"I just took whole pack\""`. Extra doses aren't in
`adherencePct`; they're counted in `extra`.

`GET /api/patients/{id}/adherence`:

```json
{"overall": { /* adherence */ },
 "byMedication": [{"reminderId": 1, "medication": "Amoxicillin 500mg", "adherence": { }}],
 "daily": [{"date": "2026-10-10", "taken": 2, "late": 0, "missed": 1, "unknown": 0,
            "extra": 0, "pending": 0}]}
```

`GET /api/patients/{id}/messages` item:

```json
{"id": 2, "direction": "out", "text": "Sorry to hear that, Sam. I've let Dr Lee know.",
 "createdAt": "2026-10-10T10:00:20Z", "inReplyToId": 1, "traceIds": [1, 2]}
```

`GET /api/flags` item:

```json
{"id": 1, "patientId": 1, "patientName": "Sam Taylor", "doseId": null,
 "kind": "side_effect", "severity": "warning", "summary": "I feel a bit nauseous",
 "resolved": false, "resolvedAt": null, "createdAt": "2026-10-10T10:00:20Z"}
```

`kind` is one of `emergency` (urgent), `missed_doses`, `extra_dose`, `over_daily_max`
(urgent), `unresponsive`, `side_effect`, `stopped_early`, `question_for_doctor`. Summaries
of patient-reported flags quote what the patient said.

- An `emergency` flag for an overdose report ("I took the whole pack") has `doseId` set to the
  `extra` dose Hermod logged for it. Other emergencies (e.g. "I can't breathe") have
  `doseId: null`. An overdose report doesn't get a separate `extra_dose` flag.
- `urgent` comes from the safety checks (`emergency`, `over_daily_max`), or from Hermod's own
  flags within 24 hours of an emergency (e.g. "not good" after an overdose). Any other flag
  Hermod raises is at most `warning`.

`GET /api/dashboard`:

```json
{"patients": 3, "linkedPatients": 2, "activeReminders": 4, "averageAdherencePct": 86,
 "openFlags": {"urgent": 1, "warning": 2, "info": 0, "total": 3},
 "needsAttention": [ /* patient list items, worst first */ ],
 "recentFlags": [ /* flags */ ],
 "recentMessages": [{"patientId": 1, "patientName": "Sam Taylor", "direction": "in",
                     "text": "took it", "createdAt": "2026-10-10T10:00:20Z"}]}
```

`needsAttention` holds patients with open urgent or warning flags, or adherence under 80%.

## Frontend integration

- **Config (Vite env):** `VITE_API_URL`, default `http://localhost:8000`. `VITE_API_KEY` is
  optional; if set, send it as `X-API-Key` (only needed when the backend has `API_KEY`).
- **CORS:** `http://localhost:5173` and `http://127.0.0.1:5173` are allowed by default
  (`CORS_ORIGINS`).
- **Adherence numbers the UI shows**, from any `adherence` object:
  taken = `taken + late`; due = `taken + late + missed + unknown`;
  prescribed = due + `pending`. `pending` here only counts doses whose time has passed but
  that haven't been answered yet (under 6 hours old), so "prescribed" means "prescribed so
  far". For the whole course use the reminder's `totalDoses` (per reminder: `dosesSent` = due,
  `dosesConfirmed` = taken). `adherencePct` is already `round(100 * taken / due)`.

**Run the backend locally for UI work** (fake data, never touches Supabase or Telegram):

```bash
python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev]"     # once
# Seed a fictional clinic: 12 synthetic patients with dose history
DATABASE_URL=sqlite:///./hermod-dev.db .venv/bin/python -m hermod.demo seed-clinic --reset
# Serve it: console channel (check-ins are printed), no bot token, no LLM key
DATABASE_URL=sqlite:///./hermod-dev.db CHANNEL=console TELEGRAM_BOT_TOKEN= GEMINI_API_KEY= \
  .venv/bin/uvicorn hermod.main:app --port 8000
```

Drop `TELEGRAM_BOT_TOKEN=` to use the token from `.env`: `telegramLink` is then filled in, and
`CHANNEL=console` still means no Telegram poller and nothing is sent.

**The same clinic in the shared database (Supabase).** It only adds patients and refuses to
run without `--shared`; `--reset` is SQLite only. `--remove` deletes just these demo patients
(matched by phone), leaving everyone else's data alone:

```bash
.venv/bin/python -m hermod.demo seed-clinic --shared            # add (uses .env DATABASE_URL)
.venv/bin/python -m hermod.demo seed-clinic --remove --shared   # take them out
```

Phone numbers are ACMA's reserved numbers for fiction (0491 570 156 etc.,
<https://www.acma.gov.au/use-phone-numbers-fiction>), so texting a demo patient their link
reaches no one. The UI types and shows Australian mobiles as `0491 570 156` and sends
`61491570156`.

Re-run the seed command to refresh the history (it's built relative to now). The variables on
the command line override `.env`, so the real database and bot are never used. The seed
(`hermod/demo_clinic.py`) gives a mix to design against: high and low adherence, two
medications on one patient, a Spanish-speaking patient, a patient with no reminders, a
finished course (`status: "ended"`), and patients with and without `nextAppointmentAt`.
`telegramLink` is `null` without a bot token, so show `linkCode` or a placeholder.
