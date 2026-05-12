# tools.py
# Three clinical tool functions called by GPT-4o mini during the conversation.
# All operate on in-memory mock data — no DB, no external calls.

import uuid
from app.data import PATIENTS, SLOTS, CLINIC

# ---------------------------------------------------------------------------
# TOOL 1: Patient Lookup
# ---------------------------------------------------------------------------

def lookup_patient(patient_name: str, date_of_birth: str) -> dict:
    """
    Verify a caller's identity before any booking action.
    Matches on lowercase name. DOB must match exactly.

    Returns patient record on success, error dict on failure.
    """
    key = patient_name.strip().lower()

    patient = PATIENTS.get(key)

    if not patient:
        return {
            "status": "not_found",
            "message": f"No patient record found for '{patient_name}'. "
                       f"They may not be registered at {CLINIC['name']}, "
                       f"or the name may be spelled differently.",
        }

    if patient["date_of_birth"] != date_of_birth.strip():
        return {
            "status": "dob_mismatch",
            "message": "Patient name was found but date of birth does not match. "
                       "Please ask the caller to confirm their date of birth.",
        }

    return {
        "status": "found",
        "patient_id": patient["patient_id"],
        "name": patient["name"],
        "insurance": patient["insurance"],
        "last_visit": patient["last_visit"],
        "doctor": patient["doctor"],
    }


# ---------------------------------------------------------------------------
# TOOL 2: Appointment Booking
# ---------------------------------------------------------------------------

def book_appointment(
    patient_id: str,
    preferred_date: str,
    preferred_time: str,
    reason: str,
) -> dict:
    """
    Book the first available slot on preferred_date that matches preferred_time.
    If preferred_time is not available, books the next open slot on that date.
    If no slots at all on that date, returns no_availability.

    preferred_date: YYYY-MM-DD
    preferred_time: e.g. "10:30 AM" — fuzzy matched, so "10:30" also works
    """
    # Verify patient exists
    patient = next(
        (p for p in PATIENTS.values() if p["patient_id"] == patient_id),
        None,
    )
    if not patient:
        return {
            "status": "error",
            "message": f"Patient ID '{patient_id}' not found. Run lookup_patient first.",
        }

    day_slots = SLOTS.get(preferred_date)
    if not day_slots:
        return {
            "status": "no_availability",
            "message": f"No clinic slots are scheduled for {preferred_date}. "
                       f"Available dates are: {', '.join(SLOTS.keys())}.",
        }

    available = [s for s in day_slots if s["status"] == "available"]
    if not available:
        return {
            "status": "no_availability",
            "message": f"All slots on {preferred_date} are fully booked. "
                       f"Please offer the caller another date.",
        }

    # Try to match preferred time, fall back to first available
    target = preferred_time.strip().upper()
    matched_slot = next(
        (s for s in available if target in s["time"].upper()),
        available[0],  # fallback to first open slot
    )

    # Mutate in-memory — marks slot as booked for this session
    matched_slot["status"] = "booked"
    matched_slot["booked_by"] = patient_id

    confirmation_number = f"IC-{uuid.uuid4().hex[:6].upper()}"

    return {
        "status": "confirmed",
        "confirmation_number": confirmation_number,
        "patient_name": patient["name"],
        "confirmed_date": preferred_date,
        "confirmed_time": matched_slot["time"],
        "doctor": CLINIC["doctor"],
        "location": CLINIC["location"],
        "reason": reason,
        "message": f"Appointment confirmed for {patient['name']} on {preferred_date} "
                   f"at {matched_slot['time']} with {CLINIC['doctor']}. "
                   f"Confirmation number: {confirmation_number}.",
    }


# ---------------------------------------------------------------------------
# TOOL 3: Escalation / Transfer
# ---------------------------------------------------------------------------

def escalate_call(reason: str, urgency: str) -> dict:
    """
    Escalate the call to clinical staff based on urgency level.

    urgency: "routine" | "urgent" | "emergency"
    - routine  → transfer to nurse line, normal wait
    - urgent   → priority nurse line, short wait
    - emergency → instruct caller to call 911 immediately
    """
    urgency = urgency.strip().lower()

    if urgency == "emergency":
        return {
            "status": "emergency",
            "action": "direct_to_911",
            "message": "This sounds like a medical emergency. "
                       "Please hang up and call 911 immediately, "
                       "or have someone drive you to the nearest emergency room right now.",
        }

    if urgency == "urgent":
        return {
            "status": "transferring",
            "action": "priority_nurse_line",
            "estimated_wait": "2 to 3 minutes",
            "contact": CLINIC["nursing_line"],
            "message": f"I am connecting you to our priority nursing line right now. "
                       f"Please hold — estimated wait is 2 to 3 minutes. "
                       f"Reason noted: {reason}.",
        }

    # routine
    return {
        "status": "transferring",
        "action": "nurse_line",
        "estimated_wait": "5 to 10 minutes",
        "contact": CLINIC["nursing_line"],
        "message": f"I will transfer you to our nursing team. "
                   f"Please hold — estimated wait is 5 to 10 minutes. "
                   f"Reason noted: {reason}.",
    }


# ---------------------------------------------------------------------------
# TOOL REGISTRY
# ---------------------------------------------------------------------------
# Single source of truth for tool definitions passed to OpenAI AND
# the dispatcher used by main.py to route tool_call events.

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_patient",
            "description": (
                "Look up a patient by name and date of birth to verify their identity "
                "before booking or discussing any account details. "
                "Always call this before book_appointment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Full name of the patient as stated by the caller.",
                    },
                    "date_of_birth": {
                        "type": "string",
                        "description": "Date of birth in YYYY-MM-DD format.",
                    },
                },
                "required": ["patient_name", "date_of_birth"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": (
                "Book an appointment for a verified patient. "
                "Only call this after lookup_patient has returned a valid patient_id. "
                "If the caller changes their preferred date mid-conversation, "
                "call this again with the new date — do not reuse old results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "Patient ID returned by lookup_patient.",
                    },
                    "preferred_date": {
                        "type": "string",
                        "description": "Preferred appointment date in YYYY-MM-DD format.",
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "Preferred time e.g. '10:30 AM'. If caller has no preference, pass 'any'.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for the visit e.g. 'annual checkup', 'chest pain follow-up'.",
                    },
                },
                "required": ["patient_id", "preferred_date", "preferred_time", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_call",
            "description": (
                "Transfer the caller to clinical staff or emergency services. "
                "Use urgency='emergency' if the caller describes active chest pain, "
                "difficulty breathing, or any life-threatening symptom. "
                "Use urgency='urgent' for concerning but non-emergency symptoms. "
                "Use urgency='routine' for general clinical questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief description of why the caller needs to be escalated.",
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["routine", "urgent", "emergency"],
                        "description": "Urgency level of the escalation.",
                    },
                },
                "required": ["reason", "urgency"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# DISPATCHER
# ---------------------------------------------------------------------------
# main.py calls this with the tool name and args from the OpenAI tool_call.
# Returns the result dict to be sent back as a tool message.

TOOL_MAP = {
    "lookup_patient": lookup_patient,
    "book_appointment": book_appointment,
    "escalate_call": escalate_call,
}

def run_tool(tool_name: str, args: dict) -> dict:
    fn = TOOL_MAP.get(tool_name)
    if not fn:
        return {"status": "error", "message": f"Unknown tool: '{tool_name}'"}
    return fn(**args)