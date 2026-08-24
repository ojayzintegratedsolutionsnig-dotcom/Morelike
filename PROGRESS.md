# Morelike — Project Progress Journal

> **Last updated:** 2026-08-12
> **Purpose:** Keep Claude up to speed on what's been done, what's live, and gotchas to avoid.

---

## Project Overview

**Morelike** is a YouTube video idea generator & AI script writer. Paste a YouTube channel URL → it analyzes top videos → generates scripts, titles, thumbnails, and production prompts in the creator's style.

- **Frontend URL:** https://morelikecreator.com/ (custom domain → Vercel)
- **Backend API:** https://morelike-morelike.up.railway.app/ (Railway free tier)
- **GitHub:** https://github.com/ojayzintegratedsolutionsnig-dotcom/Morelike (public, user plans to make private later)
- **Local project:** `E:\MORELIKE PROJECT\morelike-clone\`
- **Backup location:** `Z:\AI\Morelike\`

### Architecture

```
Frontend (Vercel)                    Backend (Railway)
React + Vite + Tailwind     ──→     Flask + Gunicorn + gevent
morelikecreator.com                  morelike-morelike.up.railway.app
                                     Port: 8080 (internal), mapped via Railway
```

- Frontend env vars (Vercel): `VITE_API_URL`, `VITE_LEMON_SQUEEZY_URL`, etc.
- Backend env vars (Railway): All API keys, webhook secrets, product IDs

---

## Current Deployment Status

### Backend — Railway (✅ LIVE)

| Detail | Value |
|--------|-------|
| Service | `Morelike` |
| Builder | nixpacks (v1.41.0) |
| Start command | `cd backend && gunicorn main:app -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -b 0.0.0.0:${PORT:-5002} --timeout 300` |
| Volume | `morelike-volume` mounted at `/data` (50 MB / 500 MB) |
| Region | US East |
| Python detected via | `requirements.txt` at project root |

**Railway config (`railway.toml`):**
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "cd backend && gunicorn main:app -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -b 0.0.0.0:${PORT:-5002} --timeout 300"

[service.volume]
name = "morelike-data"
mountPath = "/data"
```

### Frontend — Vercel (✅ LIVE)

| Detail | Value |
|--------|-------|
| Custom domain | `morelikecreator.com` |
| Vercel subdomain | `morelike.vercel.app` |
| Build command | `cd frontend && npm run build` |
| Output dir | `frontend/dist` |
| Config file | `vercel.json` |

---

## Critical Gotchas & Fixes (READ BEFORE DEPLOYING)

### 1. `.gitignore` `*.txt` rule blocks `requirements.txt` ⚠️

**Problem:** The `.gitignore` has `*.txt` (line 38), which excludes ALL `.txt` files including `requirements.txt`. Railway uses git for upload context → nixpacks never sees `requirements.txt` → build fails with "Nixpacks was unable to generate a build plan."

**Fix:** Added `!requirements.txt` exception after the `*.txt` rule in `.gitignore`:
```
*.txt
!requirements.txt
!frontend/public/robots.txt
```

**This cost 7 failed deploys before discovery.** Always check `.gitignore` when nixpacks can't detect a language.

### 2. DO NOT add `buildCommand` to `railway.toml` ⚠️

**Problem:** Adding `buildCommand` (e.g., `buildCommand = "pip install -r requirements.txt"`) causes nixpacks to SKIP its automatic Python detection/provisioning. The base nixpacks image doesn't have `pip` or `python` — nixpacks adds them only when it auto-detects the language.

**Fix:** Never add `buildCommand` for Python projects on Railway nixpacks. Just `builder = "nixpacks"` and nixpacks handles everything based on detecting `requirements.txt`.

### 3. Backend runs from `backend/` subdirectory

The start command does `cd backend && gunicorn main:app ...`. The root `requirements.txt` is a redirect file:
```
-r backend/requirements.txt
```
nixpacks follows this redirect and installs from `backend/requirements.txt`.

### 4. Frontend is NOT served by Railway

Only the Flask API runs on Railway. The frontend is a separate Vite/React app deployed on Vercel. There's no static file serving for the frontend on Railway — hitting `https://morelike-morelike.up.railway.app/` returns 404.

---

## Payment Integration — Lemon Squeezy

### Plans & Checkout Links

| Plan | Price | Credits | Limits | Lemon Squeezy Checkout |
|------|-------|---------|--------|------------------------|
| Basic | $8 | 3 | 3 min/video, 3 videos | `/checkout/buy/a6315998-f19d-4806-ba57-a40dd789348b` |
| Pro | $10 | 3 | 5 min/video, 5 videos | `/checkout/buy/5562929e-ce1b-4f28-a35b-90dce4371804` |
| Pro Max | $15 | 5 | 15 min/video, 5 videos | `/checkout/buy/81b9a80c-0ac7-491c-aa37-483a0dbda94a` |

Store URL: `https://morelike.lemonsqueezy.com` (blocks bots with 403, works in browser)

### Purchase Flow
1. User clicks checkout link → Lemon Squeezy checkout page
2. After payment → Lemon Squeezy sends webhook to `POST /api/webhook/lemonsqueezy` (HMAC-SHA256 signature verified)
3. Backend generates token, stores credits + plan + order_id
4. Token delivered via Resend email (`FROM_EMAIL: noreply@contact.morelikecreator.com`)
5. User enters token on site → `POST /api/validate-token` → unlocks features

### Key Railway Env Vars for Payments
| Variable | Set? | Purpose |
|----------|------|---------|
| `LEMON_SQUEEZY_WEBHOOK_SECRET` | ✅ | HMAC signature validation |
| `LEMON_SQUEEZY_PRODUCT_PRO` | ✅ | Maps product ID → 'pro' plan |
| `LEMON_SQUEEZY_PRODUCT_PROMAX` | ✅ | Maps product ID → 'promax' plan |
| `RESEND_API_KEY` | ✅ | Email delivery for tokens |
| `FROM_EMAIL` | ✅ | Sender address |

### Payment Pages in Frontend
- `/plans` — dedicated plan comparison page with all 3 "Select" buttons
- `/portal` — paywall modal ("Our Plans" button) appears when user tries to unlock

---

## Environment Variables (Railway)

```
ADMIN_PASSWORD              → Set
APIFY_API_KEY               → Set (transcript extraction)
ASSEMBLYAI_API_KEY          → Set (speech-to-text transcription)
DEEPSEEK_API_KEY            → Set (AI generation)
FROM_EMAIL                  → noreply@contact.morelikecreator.com
GROQ_API_KEY                → Set (AI fallback/alternative)
LEMON_SQUEEZY_PRODUCT_PRO   → 5562929e-ce1b-4f28-a35b-90dce4371804
LEMON_SQUEEZY_PRODUCT_PROMAX → 81b9a80c-0ac7-491c-aa37-483a0dbda94a
LEMON_SQUEEZY_WEBHOOK_SECRET → Set
RESEND_API_KEY              → Set (email)
YOUTUBE_API_KEY             → Set
```

---

## File Inventory

### Project Files (in `Z:\AI\Morelike\morelike-clone\`)
- `railway.toml` — Railway deploy config (DO NOT add buildCommand)
- `.gitignore` — has `!requirements.txt` exception (DO NOT remove)
- `requirements.txt` — redirects to `backend/requirements.txt`
- `backend/requirements.txt` — actual Python deps (flask, yt-dlp, gunicorn, gevent, openai, resend, etc.)
- `backend/main.py` — Flask app with all API routes
- `backend/.env` — local env secrets (`GROQ_API_KEY`, etc.) — gitignored
- `frontend/src/pages/Portal.jsx` — main app portal + paywall
- `frontend/src/pages/Plans.jsx` — dedicated plans page
- `vercel.json` — Vercel frontend deploy config
- `PROGRESS.md` — this file

### Marketing/External Files
- `build_marketing_pdf.py` — Reportlab PDF generator script

### Location & Backups
- `Z:\AI\Morelike\morelike-clone\` — **main project** (sole morelike project as of 2026-08-14)
- Old precursor `viral-content-cloner-agent` and 2026-05-23 backup files were deleted to Recycle Bin (2026-08-14)

---

## Key API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/status` | GET | Health check (returns idle/running/progress) |
| `/api/extract` | POST | Extract transcripts from channel |
| `/api/generate-package` | POST | Generate script package |
| `/api/generation-status/<job_id>` | GET | Poll generation progress |
| `/api/validate-token` | POST | Validate access token |
| `/api/claim-token` | POST | Claim token by email (gmail only) |
| `/api/webhook/lemonsqueezy` | POST | Lemon Squeezy purchase webhook |
| `/api/promo` | GET | Get active promo code |
| `/api/credits` | GET | Get user credits |
| `/api/channel-videos` | POST | List channel videos |
| `/api/download-package` | GET | Download generated package |

---

## Pending / TODO

- [ ] Make GitHub repo private (user will handle via GitHub settings)
- [ ] Test full purchase flow end-to-end (buy → webhook → token → unlock)
- [ ] Update README.md to reflect current deployment (not just local dev)
- [ ] Consider adding `/api/health` endpoint (currently only `/api/status` exists)

---

## Session Log

### 2026-08-24
- **Fixed backend entrypoint alias**: Created `backend/app.py` pointing to `backend/main.py`. Updated `start.bat`, `README.md`, and `QUICKSTART.md` to reference `python main.py` and the correct local ports (`5002` backend, `3100` frontend).

### 2026-08-14
- Replaced Groq API key → new key (`backend/.env` + Railway env var `GROQ_API_KEY`)
- **Fixed image upload / vision analysis**: `call_groq_vision` model changed from `meta-llama/llama-4-scout-17b-16e-instruct` (not accessible on the current Groq key) → `qwen/qwen3.6-27b` (the vision-capable model the key can access). Verified live: returns valid JSON from an image.
- Created `backend/.env` with `GROQ_API_KEY` (gitignored, auto-loaded via `load_dotenv()`).
- **Deployed backend to Railway** — deploy ID `a72c6f93-67f8-423b-9977-21ec7daaa49a` SUCCESS, service Online (old `57153dde` removed).
- Verified live: `https://morelike-morelike.up.railway.app/api/status` → `{"status":"idle"}`
- **Consolidated projects**: deleted old `viral-content-cloner-agent/` + 2026-05-23 backup files (`.env.secrets`, `RESTORE_GUIDE.md`, `MORELIKE_PROGRESS.md`, `MORELIKE_MARKETING_VIDEO.md/.pdf`, `landing_page_bg.png`) → Recycle Bin.
- `Z:\AI\Morelike\morelike-clone` is now the sole main morelike project. **Convention:** update this PROGRESS.md + memory after every successful edit.
- **Fixed "Fetch Transcript unclickable"** (user pasted a *video* URL, not a channel URL → backend returned 0 videos → `0 / 0` screen): `backend/extractor.py` `_extract_channel_handle` + `_get_viral_videos_api` now accept video URLs (`youtube.com/watch?v=` / `youtu.be/`), resolve the video → its channel via YouTube API, and put the pasted video first in the list. **Deployed** (deploy ID `23e3c3cf-d023-408a-857d-1cb713698fb7` SUCCESS) and verified live: `https://www.youtube.com/watch?v=Gfcybr0q-HA` → returns the CoComelon video + 2 channel top videos. Also noted: deployed frontend (`index-DkKn_ptP.js`) is an older build than local `Portal.jsx` (missing the empty-state fallback UI).
- **Added AssemblyAI speech-to-text transcription** (`backend/extractor.py`): new `_extract_transcript_via_assemblyai(video_id)` — yt-dlp downloads bestaudio (raw, no ffmpeg needed; `bestaudio[ext=m4a]/bestaudio/best`, skips videos >90 min to protect the free allowance) → uploads to AssemblyAI → submits transcription job → polls until completed. Wired into `get_transcript()` as the reliable fallback when YouTube captions fail (works on videos with **no captions at all**, no bot-blocking). Also added as **Method 2** in `/api/admin/debug-transcript`. Key `ASSEMBLYAI_API_KEY` added to `backend/.env` (gitignored) + Railway env var. Free tier ≈ 500+ min/month. **Deployed** (deploy ID `d6dead14-0db3-40eb-b6c6-4cb1e736d094` SUCCESS; auto-triggered `49b1019e` removed) — verified live via `/api/status` → idle. Note: AssemblyAI upload/submit/poll flow verified locally (all 200); only the yt-dlp audio download is blocked locally by a Windows Python 3.10 SSL cert quirk (works fine on Railway/Linux).

### 2026-08-11 / 2026-08-12
- Recreated `MORELIKE_MARKETING_VIDEO.md` (was deleted by `git rm`)
- Regenerated `MORELIKE_MARKETING_VIDEO.pdf` with Fish Audio + text-to-video content
- **Fixed Railway deploy:** Discovered `.gitignore` `*.txt` rule was blocking `requirements.txt`. Added `!requirements.txt` exception.
- **Deployed backend successfully** to Railway (deploy ID: `57153dde-4aa7-4890-9b3c-fb4ad6b55985`)
- Verified backend at `https://morelike-morelike.up.railway.app/api/status` — returns `{"status":"idle"}`
- Found frontend URLs: `https://morelike.vercel.app` and `https://morelikecreator.com/`
- Verified all Lemon Squeezy env vars and payment links are configured correctly
- Created this PROGRESS.md file
- Created backup to `Z:\AI\Morelike\`

### Prior Sessions
- Built client-side transcript fetcher to work around YouTube IP blocking
- Integrated client-fetched transcripts into frontend flow
- Updated backend to handle client-fetched transcripts
- Created marketing video production package
- Multiple Railway deploy attempts before finding the `.gitignore` root cause
