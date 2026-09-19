# Natural Teacher Avatar And Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Make the draggable avatar feel like a calm young teacher instead of a restless desktop pet, and make the cloned voice speak with gentler pacing and more natural Chinese pauses.

**Architecture:** Keep the existing two-frame avatar renderer, drag behavior, face overlay, and GPT-SoVITS service. Narrow autonomous movement to three restrained teacher gestures, replace tap hopping with a brief acknowledgment nod, slow the speaking body cadence, and send a conservative natural-speech preset plus punctuation-normalized text to GPT-SoVITS.

**Tech Stack:** Vanilla JavaScript and CSS, FastAPI/Python, GPT-SoVITS API v2, Python `unittest`, Node `vm` runtime checks.

---

### Task 1: Lock the young-teacher motion contract with failing tests

**Files:**
- Modify: `tests/test_avatar_frontend.py`
- Modify: `tests/avatar_runtime.cjs`

- [x] Replace the old pet-action expectations with `glance`, `posture`, and `nod` only.
- [x] Assert that tapping produces `acknowledge`, not `hop`.
- [x] Assert autonomous actions wait 14–24 seconds and never start gait roaming.
- [x] Assert pointer parallax stays subtle and speaking/celebration animations use restrained timing.
- [x] Run `python -m unittest tests.test_avatar_frontend -v` and confirm the new assertions fail for the old behavior.

### Task 2: Implement restrained young-teacher motion

**Files:**
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`
- Modify: `app/static/index.html`

- [x] Replace idle action specs with weighted `glance`, `posture`, and `nod` gestures using the idle pose.
- [x] Remove automatic sidestep handling from the idle loop while preserving user drag placement.
- [x] Rename the tap helper/state to a teacher acknowledgment and show “点头回应” during it.
- [x] Reduce pointer depth/rotation, slow body speaking cadence, soften correction/celebration, and add a dedicated acknowledgment keyframe.
- [x] Widen randomized blink timing so its cadence feels less regular.
- [x] Update static asset cache versions.
- [x] Re-run `python -m unittest tests.test_avatar_frontend -v` and confirm the motion tests pass.

### Task 3: Lock the natural GPT-SoVITS request with failing tests

**Files:**
- Modify: `tests/test_tts.py`
- Modify: `tests/test_speech_api.py`

- [x] Add a unit test showing headings, list breaks, and missing final punctuation become speakable Chinese pauses.
- [x] Capture the GPT-SoVITS request URL and assert `top_k=15`, `top_p=0.9`, `temperature=0.85`, `fragment_interval=0.42`, `repetition_penalty=1.3`, and the normalized text.
- [x] Change the expected default teacher speed to `0.94`.
- [x] Run `python -m unittest tests.test_tts tests.test_speech_api -v` and confirm the new assertions fail for the old request.

### Task 4: Implement natural cloned-voice pacing

**Files:**
- Modify: `app/tts.py`
- Modify: `app/main.py`
- Modify: `app/static/admin.html`
- Modify: `app/static/admin.js`
- Modify: `data/settings.json`

- [x] Add `naturalize_speech_text()` that removes visual-only markup while turning headings/list/newline boundaries into short spoken pauses and appending terminal punctuation.
- [x] Send the conservative sampling, repetition, and fragment-pause parameters to GPT-SoVITS.
- [x] Change every application/UI/default fallback speed from `0.96` or the saved `1.0` to `0.94` without changing the selected teacher sample.
- [x] Re-run `python -m unittest tests.test_tts tests.test_speech_api -v` and confirm the voice tests pass.

### Task 5: Verify the complete experience and record the work

**Files:**
- Modify: `README.md`
- Modify: `MEMORY.md`

- [x] Run `python -m unittest discover -s tests -v`.
- [x] Restart or confirm the local web process, request `/api/admin/voice-service-status`, and synthesize a fresh teacher preview.
- [x] Open the classroom page, observe an idle gesture and tap acknowledgment, and confirm drag still works.
- [x] Document the natural-teacher motion policy, the GPT-SoVITS preset, the verification commands/results, and any remaining limitation.
- [x] Review `git diff --check` and `git status --short` before handoff.
