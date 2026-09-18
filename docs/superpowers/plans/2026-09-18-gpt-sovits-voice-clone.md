# GPT-SoVITS Voice Clone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install the official GPT-SoVITS runtime locally, connect it to the existing authorized teacher sample, and produce a verified cloned-voice WAV from the product.

**Architecture:** Keep the third-party repository, Conda environment, model weights, logs, and generated audio outside Git while exposing repeatable PowerShell setup/start commands in this repository. Reuse the existing `app.tts.synthesize_gpt_sovits` adapter, which already matches the official `/tts` API, and add a service probe so the admin page distinguishes “sample configured” from “GPT-SoVITS running.”

**Tech Stack:** Windows PowerShell, Conda Python 3.10, CUDA 12.8 PyTorch, official GPT-SoVITS `api_v2.py`, FastAPI, vanilla JavaScript, unittest.

---

## File Structure

- `scripts/setup-gpt-sovits.ps1`: clone/update the official source and invoke its official CU128 installer.
- `scripts/start-gpt-sovits.ps1`: start `api_v2.py` on localhost:9880, wait for readiness, and keep logs local.
- `app/tts.py`: provide a bounded service-health probe while preserving the existing official `/tts` request contract.
- `app/main.py`: expose authenticated service status to the teacher console.
- `app/static/admin.html`, `app/static/admin.js`, `app/static/admin.css`: show runtime status and a clear start command next to voice settings.
- `tests/test_tts.py`, `tests/test_speech_api.py`, `tests/test_admin_frontend.py`: cover the probe, authenticated endpoint, and UI contract.
- `.gitignore`: exclude `.local/GPT-SoVITS`, models, logs, and generated preview audio.
- `README.md`, `MEMORY.md`: document operation, consent boundary, verification, and limitations.

### Task 1: Reproducible local runtime scripts

**Files:**
- Create: `scripts/setup-gpt-sovits.ps1`
- Create: `scripts/start-gpt-sovits.ps1`
- Modify: `.gitignore`

- [x] **Step 1: Add script contract tests**

Add assertions to `tests/test_tts.py` that both scripts exist, select `CU128`, bind only `127.0.0.1`, use port `9880`, and never embed the teacher transcript or sample filename.

- [x] **Step 2: Run the script contract tests and observe failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tts`

Expected: FAIL because the scripts do not exist.

- [x] **Step 3: Implement setup and start scripts**

The setup script must resolve `.local/GPT-SoVITS`, clone `https://github.com/RVC-Boss/GPT-SoVITS.git` if absent, create/verify Conda environment `GPTSoVits` with Python 3.10, and run the official `install.ps1 -Device CU128 -Source ModelScope` without UVR5. The start script must run `conda run -n GPTSoVits python api_v2.py -a 127.0.0.1 -p 9880`, redirect logs to `data/logs`, and poll `http://127.0.0.1:9880/docs` for at most 120 seconds.

- [x] **Step 4: Run script contract tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tts`

Expected: PASS.

### Task 2: Voice-service observability

**Files:**
- Modify: `app/tts.py`
- Modify: `app/main.py`
- Modify: `tests/test_tts.py`
- Modify: `tests/test_speech_api.py`

- [x] **Step 1: Write failing health-probe tests**

Test that `gpt_sovits_status("http://127.0.0.1:9880")` requests `/docs` with a short timeout, returns `{running: true}` on HTTP 200, and returns `{running: false, detail: ...}` on connection errors. Test that `/api/admin/voice-service-status` requires the teacher password.

- [x] **Step 2: Run the targeted tests and observe failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tts tests.test_speech_api`

Expected: FAIL because the probe and endpoint do not exist.

- [x] **Step 3: Implement the probe and endpoint**

Use `urllib.request.urlopen` with a 2-second timeout and do not send sample data. Return only running state, configured URL, and a concise local error. Protect the endpoint with `require_admin`.

- [x] **Step 4: Run targeted tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_tts tests.test_speech_api`

Expected: PASS.

### Task 3: Teacher-console runtime status

**Files:**
- Modify: `app/static/admin.html`
- Modify: `app/static/admin.js`
- Modify: `app/static/admin.css`
- Modify: `tests/test_admin_frontend.py`

- [x] **Step 1: Write a failing UI contract test**

Assert the page contains `voiceServiceStatus`, the script calls `/api/admin/voice-service-status`, and the UI explains the exact `scripts/start-gpt-sovits.ps1 -Background` command without exposing local sample paths.

- [x] **Step 2: Run the UI test and observe failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_admin_frontend`

Expected: FAIL because the status UI is absent.

- [x] **Step 3: Implement status rendering**

Render “服务已运行” or “服务未启动” with accessible text, refresh it when voice settings are loaded, and retain the existing “生成试听” flow as the end-to-end test.

- [x] **Step 4: Run the UI test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_admin_frontend`

Expected: PASS.

### Task 4: Install and verify zero-shot teacher voice

**Files:**
- Modify: `README.md`
- Modify: `MEMORY.md`

- [x] **Step 1: Run the official installation**

Run: `powershell -ExecutionPolicy Bypass -File .\scripts\setup-gpt-sovits.ps1`

Expected: the repository exists under `.local/GPT-SoVITS`, Conda environment reports Python 3.10, CUDA PyTorch is importable, FFmpeg is available inside the environment, and pretrained models exist.

- [x] **Step 2: Start the local API**

Run: `powershell -ExecutionPolicy Bypass -File .\scripts\start-gpt-sovits.ps1 -Background`

Expected: `http://127.0.0.1:9880/docs` responds and the process remains bound to localhost only.

- [x] **Step 3: Generate an authorized preview**

Derive a clean 7.4-second reference from the authorized 17-second source, then call the existing app voice-test endpoint with “你好，我是西西老师。我们一起学习编程。” Save only the app-generated cache WAV and verify its RIFF header, nontrivial size, duration, and sample rate.

- [x] **Step 4: Run full regression verification**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests`, `node --check app/static/app.js`, `node --check app/static/admin.js`, `node tests/avatar_runtime.cjs`, and `git diff --check`.

Expected: all commands exit 0.

- [x] **Step 5: Document evidence and limitations**

Document the official source revision, environment/GPU choice, preview properties, and that the result is zero-shot from 17 seconds of authorized audio. State that a one-minute clean recording and fine-tuning remain optional quality improvements, not completed facts.
