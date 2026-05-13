# main.py
# FastAPI app with a single WebSocket endpoint that Retell connects to.
# This is the entire server — event router, response streamer, tool dispatcher.

import json
import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.llm import stream_response

load_dotenv()

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
# Structured logs so you can see tool calls and events in your terminal
# during the Loom recording. Keep it clean — founders notice messy logs.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("iclinic")

# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------

app = FastAPI(title="iClinic Voice AI", version="1.0.0")

# CORS — needed if Retell's browser SDK makes preflight requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------
# Retell and FastAPI Cloud both ping this to confirm the server is alive.

@app.get("/")
async def health():
    return {"status": "ok", "service": "iClinic Voice AI"}

# ---------------------------------------------------------------------------
# RETELL WEBSOCKET ENDPOINT
# ---------------------------------------------------------------------------
# Retell opens one WebSocket per call and keeps it open for the entire call.
# Every time the caller finishes speaking, Retell sends a response_required
# event with the full conversation history. We stream tokens back immediately.

@app.websocket("/llm-websocket/{call_id}")
async def llm_websocket(websocket: WebSocket, call_id: str):
    await websocket.accept()
    log.info(f"📞  Call started — call_id={call_id}")

    # Track the active response_id so we can detect barge-in.
    # If Retell sends a new response_required while we are still streaming,
    # the response_id changes — we stop the old stream and start fresh.
    current_response_id = None

    try:
        async for raw_message in websocket.iter_text():
            event = json.loads(raw_message)
            event_type = event.get("interaction_type") or event.get("type")

            # ----------------------------------------------------------------
            # CALL STARTED
            # ----------------------------------------------------------------
            if event_type == "call_started":
                log.info("✅  call_started received")
                # Retell expects an immediate response to kick off the greeting
                await send_text(
                    websocket,
                    response_id=event.get("response_id", 0),
                    text="",
                    done=True,
                )
                continue

            # ----------------------------------------------------------------
            # RESPONSE REQUIRED
            # ----------------------------------------------------------------
            # Caller finished speaking (or call just started after greeting).
            # Pull conversation history, stream Claude's response back.

            if event_type == "response_required" or event_type == "reminder_required":
                response_id = event.get("response_id")
                current_response_id = response_id

                conversation_history = event.get("transcript", [])

                log.info(
                    f"🎤  response_required  response_id={response_id}  "
                    f"turns={len(conversation_history)}"
                )

                # Stream response token by token
                async for kind, payload in stream_response(conversation_history):

                    # Barge-in detection:
                    # If response_id has changed while we were streaming,
                    # the caller interrupted. Stop sending the old response.
                    if current_response_id != response_id:
                        log.info(f"🛑  Barge-in detected — stopping response_id={response_id}")
                        break

                    if kind == "text":
                        await send_text(
                            websocket,
                            response_id=response_id,
                            text=payload,
                            done=False,
                        )

                    elif kind == "tool_call":
                        log.info(
                            f"🔧  Tool called: {payload['tool']}  "
                            f"args={json.dumps(payload['args'])}  "
                            f"result={json.dumps(payload['result'])}"
                        )
                        # Tool result is already appended to messages inside llm.py.
                        # No need to send anything to Retell for tool calls —
                        # they are invisible to the caller. GPT continues streaming.

                    elif kind == "done":
                        await send_text(
                            websocket,
                            response_id=response_id,
                            text="",
                            done=True,
                        )
                        log.info(f"✔️   Response complete  response_id={response_id}")

                continue

            # ----------------------------------------------------------------
            # CALL ENDED
            # ----------------------------------------------------------------
            if event_type == "call_ended":
                log.info("📴  Call ended")
                break

            # ----------------------------------------------------------------
            # UPDATE ONLY — live transcript update while user is speaking
            # ----------------------------------------------------------------
            if event_type == "update_only":
                continue   # nothing to do, Retell is just keeping us in sync

            # ----------------------------------------------------------------
            # UNKNOWN EVENT — log and ignore
            # ----------------------------------------------------------------
            log.warning(f"⚠️   Unknown event type: {event_type}  raw={raw_message[:120]}")

    except WebSocketDisconnect:
        log.info("🔌  WebSocket disconnected")

    except Exception as e:
        log.error(f"❌  Unexpected error: {e}", exc_info=True)

    finally:
        log.info("🏁  WebSocket handler exiting")


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

async def send_text(websocket: WebSocket, response_id: int, text: str, done: bool):
    """
    Send a response chunk to Retell over the WebSocket.

    Retell expects this exact shape for every chunk:
      {
        "response_id": <int matching the request>,
        "content":     <str token or empty string>,
        "content_complete": <bool — True only on the final chunk>
      }

    Send done=True with empty content to signal end of turn.
    """
    await websocket.send_text(
        json.dumps({
            "response_id": response_id,
            "content": text,
            "content_complete": done,
        })
    )