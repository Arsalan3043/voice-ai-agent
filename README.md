# iClinic Voice AI Receptionist

A production-ready voice AI agent for a cardiology clinic. Handles patient verification, appointment booking, and clinical escalation over a real phone or browser call — in real time.

Built with FastAPI, GPT-4o mini, and Retell AI.

---

## Demo

The agent handles a full clinical receptionist workflow:

- Greets the caller warmly and asks how it can help
- Verifies patient identity (name + date of birth) before any action
- Books appointments from available slots
- Handles mid-sentence interruptions (barge-in) gracefully
- Escalates clinical symptoms immediately with urgency triage
- Never gives medical advice — hard boundary enforced in the system prompt

---

## Architecture

```
Caller (Browser / Phone)
        ↓  WebRTC audio
Retell AI  ──────────────────────────────────────────────
│  STT (Deepgram)     VAD + Barge-in     TTS (ElevenLabs) │
└─────────────────────────────────────────────────────────┘
        ↓  WebSocket  (response_required event)
FastAPI Server  (FastAPI Cloud)
│  main.py — WebSocket handler + event router
│  llm.py  — GPT-4o mini streaming
│  tools.py — patient lookup, booking, escalation
└─────────────────────────────────────────────────────────
        ↓  tool calls
Data Layer  (in-memory mock)
│  data.py — patients dict, appointment slots, clinic info
└─────────────────────────────────────────────────────────
```

**End-to-end latency target:** under 500ms  
**STT:** < 200ms | **LLM first token:** < 300ms | **TTS:** < 100ms

---

## Tech Stack

| Layer | Technology |
|---|---|
| Voice platform | Retell AI (STT, VAD, TTS, barge-in) |
| LLM | GPT-4o mini via OpenAI API |
| Backend | Python 3.10 + FastAPI |
| Real-time transport | WebSocket (persistent per call) |
| Deployment | FastAPI Cloud |
| Data | In-memory Python dicts (mock) |

---

## Project Structure

```
voice-ai-agent/
├── requirements.txt          # Python dependencies
├── pyproject.toml            # FastAPI Cloud entrypoint config
├── .python-version           # Python 3.10
├── .env.example              # Environment variable template
├── .gitignore                # Excludes .env and venv
├── .fastapicloudignore       # Excludes venv from deployment
└── app/
    ├── __init__.py
    ├── main.py               # FastAPI app + WebSocket handler
    ├── llm.py                # OpenAI streaming + tool call handling
    ├── tools.py              # 3 clinical tools + dispatcher
    ├── data.py               # Mock patients, slots, clinic info
    └── prompt.py             # Aria's clinical system prompt
```

---

## Clinical Tools

### 1. `lookup_patient`
Verifies caller identity before any booking action.

| Parameter | Type | Description |
|---|---|---|
| `patient_name` | string | Full name as stated by caller |
| `date_of_birth` | string | In YYYY-MM-DD format |

Returns patient ID, insurance type, last visit date, and assigned doctor on success. Returns `not_found` or `dob_mismatch` on failure.

### 2. `book_appointment`
Books an available slot for a verified patient.

| Parameter | Type | Description |
|---|---|---|
| `patient_id` | string | Returned by `lookup_patient` |
| `preferred_date` | string | In YYYY-MM-DD format |
| `preferred_time` | string | e.g. "10:30 AM" |
| `reason` | string | Brief reason for visit |

Returns confirmation number, confirmed datetime, doctor name, and location. Mutates the in-memory slot to mark it booked for the session.

### 3. `escalate_call`
Transfers caller to clinical staff or emergency services.

| Parameter | Type | Description |
|---|---|---|
| `reason` | string | Why the caller needs escalation |
| `urgency` | enum | `routine` / `urgent` / `emergency` |

- `emergency` → instructs caller to call 911 immediately
- `urgent` → transfers to priority nursing line, 2-3 min wait
- `routine` → transfers to nursing team, 5-10 min wait

---

## Key Design Decisions

**Barge-in handling** — Retell cancels TTS audio the moment the caller speaks. The server detects the new `response_id` on every token before sending and stops streaming the old response immediately. No extra code required.

**Role remapping** — Retell sends conversation history with role `"agent"` for assistant turns. This is remapped to `"assistant"` before passing to OpenAI, which only accepts standard role names.

**Tool definitions in `tools.py`** — The OpenAI tool schema and the Python function that executes it live in the same file, right next to each other. Adding a new tool means touching one file only.

**System prompt written for ears not eyes** — No bullet points, no colons, no markdown anywhere in what Aria says. Every output sentence is designed to sound natural when spoken by a TTS voice. Short sentences, natural fillers while tools run, human-readable dates and times.

**Clinical safety is unconditional** — Emergency escalation fires before finishing any other flow. If a caller mentions chest pain mid-booking, the booking stops and escalation fires immediately.

**`max_tokens=150`** — Hard cap on response length. Voice responses must be short. The system prompt instructs Aria to be concise, but this is the safety net.

**`temperature=0.4`** — Low enough for consistent clinical tone, high enough that responses don't sound scripted.

---

## Local Development Setup

### Prerequisites
- Python 3.10
- OpenAI API key
- Retell AI account (free tier available)
- ngrok (for exposing local server to Retell)

### 1. Clone and set up environment

```bash
git clone https://github.com/your-username/voice-ai-agent.git
cd voice-ai-agent

python3.10 -m venv voiceai
source voiceai/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and add your OpenAI key:

```
OPENAI_API_KEY=sk-your-actual-key-here
```

### 3. Start the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
```

You should see:
```
INFO:     Application startup complete.
```

### 4. Expose locally with ngrok

```bash
# In a separate terminal tab — keep this running
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL. This is your webhook URL for Retell.

> **Note:** ngrok URLs change on every restart. Keep the ngrok tab open during development. Use a fixed subdomain (`ngrok http --domain=your-name.ngrok-free.app 8000`) to avoid re-pasting into Retell every time.

---

## Retell AI Dashboard Setup

1. Go to [retellai.com](https://retellai.com) and create an account
2. Create a new Agent — name it `iClinic Receptionist`
3. Set agent type to **Custom LLM**
4. Set LLM WebSocket URL:
   - Local dev: `wss://xxxx.ngrok-free.app/llm-websocket`
   - Production: `wss://voice-ai-agent.fastapicloud.dev/llm-websocket`
5. Choose voice — `Ella` or `Matilda` recommended
6. Set end-of-speech sensitivity to `High` for lower latency
7. Save and click **Test**

> Tools are handled entirely server-side. No tool configuration needed in the Retell dashboard for Custom LLM agents.

---

## Deployment (FastAPI Cloud)

### First-time deployment

```bash
# Install FastAPI Cloud CLI
pip install "fastapi[standard]"

# Login
fastapi login

# Set your OpenAI key as an encrypted secret
fastapi cloud env set --secret OPENAI_API_KEY "sk-your-actual-key-here"

# Deploy
fastapi deploy
```

Your app will be live at `https://voice-ai-agent.fastapicloud.dev`

### Managing the deployment

```bash
# Stop the server (saves costs when not in use)
fastapi cloud app stop

# Start the server
fastapi cloud app start

# Check status
fastapi cloud app status

# View live logs
fastapi cloud app logs

# Redeploy after code changes
fastapi deploy
```

> The URL never changes when stopping and starting. Only deleting and recreating the app changes the URL.

### Update environment variables

```bash
fastapi cloud env set --secret OPENAI_API_KEY "sk-new-key"
fastapi deploy   # redeploy to pick up new value
```

---

## Mock Data

The demo uses in-memory mock data. No database required.

### Patients

| Name | DOB | Patient ID | Insurance |
|---|---|---|---|
| Priya Sharma | 1988-04-12 | P001 | BlueCross BlueShield |
| James Wilson | 1975-09-22 | P002 | Aetna |
| Fatima Al-Hassan | 1992-07-30 | P003 | United Healthcare |
| Carlos Rivera | 1965-03-05 | P004 | Medicare |
| Linda Chen | 1980-12-18 | P005 | Cigna |
| David Park | — | — | Not registered (use to demo failed lookup) |

### Available Appointment Slots

| Date | Day | Available Times |
|---|---|---|
| 2025-06-03 | Tuesday | 10:30 AM, 2:00 PM |
| 2025-06-05 | Thursday | 9:00 AM, 1:00 PM, 4:00 PM |
| 2025-06-06 | Friday | 8:30 AM, 10:00 AM, 4:30 PM |

> Booked slots reset on every server restart — clean slate for each demo run.

---

## Demo Script

Use this flow to showcase all features in one call:

| Time | You say | What it shows |
|---|---|---|
| 0:00 | *"Hi, I'd like to book an appointment"* | Warm greeting, professional persona |
| 0:15 | *"James Wilson, September twenty-second nineteen seventy-five"* | Patient verification tool fires |
| 0:40 | *(Aria offers Thursday — interrupt mid-sentence)* "Actually, can we do Tuesday instead?" | **Barge-in** — agent stops instantly, adapts |
| 1:00 | *"Ten thirty works"* | Booking confirmed, confirmation number given |
| 1:15 | *"Also, I've been having chest pain since yesterday"* | Immediate clinical escalation |

Total call length: ~90 seconds. Clean, tight, covers every feature.

---

## What This Becomes in Production

| Feature | Current (Demo) | Production |
|---|---|---|
| Patient data | In-memory dict | Epic / Athena EHR integration |
| Appointment slots | Hardcoded mock | Real calendar + scheduling system |
| Call logging | Terminal stdout | HIPAA-compliant audit trail |
| Multi-specialty | Single cardiology | Routing layer for any specialty |
| Clinic config | Hardcoded | Onboarding layer, any clinic configures own agent |
| Authentication | None | JWT + role-based access |

---

## Troubleshooting

**`fastapi: not found` on FastAPI Cloud**
Ensure `requirements.txt` has `fastapi[standard]` not just `fastapi`.

**403 on WebSocket connection**
Your route must accept the call ID suffix Retell appends:
```python
@app.websocket("/llm-websocket/{call_id}")
async def llm_websocket(websocket: WebSocket, call_id: str):
```

**`Invalid value: 'agent'` from OpenAI**
Retell sends role `"agent"` — remap to `"assistant"` before passing to OpenAI:
```python
remapped_history = [
    {**msg, "role": "assistant"} if msg.get("role") == "agent" else msg
    for msg in conversation_history
]
```

**High latency on local dev**
Expected — ngrok adds 100-300ms. Deploy to FastAPI Cloud for production-level latency. Also set Retell end-of-speech sensitivity to `High`.

**GPT using wrong patient_id in booking**
The system prompt must explicitly instruct the model to use the exact `patient_id` string returned by `lookup_patient`. GPT-4o mini does not reliably infer this without explicit instruction.

---

## License

MIT
