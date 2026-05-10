# data.py
# Mock data for iClinic demo — no database needed
# All in-memory dicts. Slots are marked booked=True after use.

# ---------------------------------------------------------------------------
# PATIENTS
# ---------------------------------------------------------------------------
# Keyed by lowercase full name for fuzzy matching from voice input.
# Include one failed-lookup case (caller not in system) for the demo.

PATIENTS = {
    "priya sharma": {
        "patient_id": "P001",
        "name": "Priya Sharma",
        "date_of_birth": "1988-04-12",
        "insurance": "BlueCross BlueShield",
        "last_visit": "2024-11-03",
        "doctor": "Dr. Arjun Mehta",
    },
    "james wilson": {
        "patient_id": "P002",
        "name": "James Wilson",
        "date_of_birth": "1975-09-22",
        "insurance": "Aetna",
        "last_visit": "2025-01-15",
        "doctor": "Dr. Arjun Mehta",
    },
    "fatima al-hassan": {
        "patient_id": "P003",
        "name": "Fatima Al-Hassan",
        "date_of_birth": "1992-07-30",
        "insurance": "United Healthcare",
        "last_visit": "2024-08-19",
        "doctor": "Dr. Arjun Mehta",
    },
    "carlos rivera": {
        "patient_id": "P004",
        "name": "Carlos Rivera",
        "date_of_birth": "1965-03-05",
        "insurance": "Medicare",
        "last_visit": "2025-02-28",
        "doctor": "Dr. Arjun Mehta",
    },
    "linda chen": {
        "patient_id": "P005",
        "name": "Linda Chen",
        "date_of_birth": "1980-12-18",
        "insurance": "Cigna",
        "last_visit": "2024-06-10",
        "doctor": "Dr. Arjun Mehta",
    },
    # P006 intentionally missing — use "David Park" to demo failed lookup
}

# ---------------------------------------------------------------------------
# APPOINTMENT SLOTS
# ---------------------------------------------------------------------------
# Keyed by date string (YYYY-MM-DD). Each slot has a time, status, and
# optional booked_by field. "available" slots can be booked.

SLOTS = {
    "2025-06-03": [  # Tuesday
        {"slot_id": "S001", "time": "09:00 AM", "status": "booked",    "booked_by": "P002"},
        {"slot_id": "S002", "time": "10:30 AM", "status": "available", "booked_by": None},
        {"slot_id": "S003", "time": "02:00 PM", "status": "available", "booked_by": None},
        {"slot_id": "S004", "time": "03:30 PM", "status": "booked",    "booked_by": "P004"},
    ],
    "2025-06-05": [  # Thursday
        {"slot_id": "S005", "time": "09:00 AM", "status": "available", "booked_by": None},
        {"slot_id": "S006", "time": "11:00 AM", "status": "booked",    "booked_by": "P003"},
        {"slot_id": "S007", "time": "01:00 PM", "status": "available", "booked_by": None},
        {"slot_id": "S008", "time": "04:00 PM", "status": "available", "booked_by": None},
    ],
    "2025-06-06": [  # Friday
        {"slot_id": "S009", "time": "08:30 AM", "status": "available", "booked_by": None},
        {"slot_id": "S010", "time": "10:00 AM", "status": "available", "booked_by": None},
        {"slot_id": "S011", "time": "02:30 PM", "status": "booked",    "booked_by": "P001"},
        {"slot_id": "S012", "time": "04:30 PM", "status": "available", "booked_by": None},
    ],
}

# ---------------------------------------------------------------------------
# CLINIC INFO
# ---------------------------------------------------------------------------
CLINIC = {
    "name": "iClinic Cardiology Center",
    "doctor": "Dr. Arjun Mehta",
    "specialty": "Interventional Cardiology",
    "location": "Suite 410, 3200 Southwest Freeway, Houston, TX 77027",
    "nursing_line": "+1 (713) 555-0192",
}