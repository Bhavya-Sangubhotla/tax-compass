from tax_search import search_tax_documents
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import logging
from dotenv import load_dotenv
import os

load_dotenv()  # loads GOOGLE_API_KEY from .env into os.environ

# ── Logging setup ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tax_assistant")

# Initialize FastAPI instance (aliased to both 'app' and 'api' for uvicorn compatibility)
app = FastAPI(title="Tax Assistant API")
api = app

# Enable CORS middleware so the React frontend can perform fetch requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dynamic state tracking UI selection (populated via UI HTTP requests)
selected_service: str = "itr-filing"
user_documents: List[str] = []
added_documents: List[str] = []

def update_user_selection(service_id: str, u_docs: Optional[List[str]] = None, a_docs: Optional[List[str]] = None):
    global selected_service, user_documents, added_documents
    if service_id:
        selected_service = service_id
    if u_docs is not None:
        user_documents = u_docs
    if a_docs is not None:
        added_documents = a_docs

# Request model for user added documents
class DocumentPayload(BaseModel):
    user_documents: Optional[List[str]] = []
    added_documents: Optional[List[str]] = []

# Request / response models for the chat flow
class ChatMessageRequest(BaseModel):
    session_id: Optional[str] = None   # None → start a new session
    message: str                        # User's text (situation or follow-up answer)

class ChatMessageResponse(BaseModel):
    session_id: str
    reply: str                          # Chatbot's next question / response
    is_complete: bool                   # True when enough info has been collected
    profile: Optional[Dict[str, Any]] = None  # Populated once is_complete is True

# =====================================================================
# DYNAMIC DOCUMENTS DATABASE FOR ITR FILING
# =====================================================================
DOCUMENTS = {
    "common": [
        "Form 26AS",
        "AIS",
        "Bank Statements"
    ],
    "salary": [
        "Form 16",
        "Form 16A",
        "Pay Slips"
    ],
    "home_loan": [
        "Housing Loan Interest Certificate"
    ],
    "rent": [
        "Rent Receipts",
        "Rental Agreement"
    ],
    "investments": [
        "Investment / Premium Payment Receipts"
    ],
    "capital_gains": [
        "Capital Gains Statement",
        "Broker / Securities Transaction Statement"
    ],
    "house_property": [
        "Tenant / Rent Details",
        "Municipal / Local Tax Payment Details",
        "Home Loan Interest Details"
    ],
    "business": [
        "Business Income Records",
        "Expense Records",
        "Profit & Loss / Financial Records"
    ]
}

def get_itr_documents_for_profile(profile: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Dynamically generates the tailored list of required documents for ITR filing
    based on the user's financial profile.
    """
    if not profile:
        # Default baseline if no profile is available yet
        return DOCUMENTS["common"] + DOCUMENTS["salary"]

    docs: List[str] = []

    # 1. Common documents (always needed for every ITR filer)
    docs.extend(DOCUMENTS["common"])

    emp = profile.get("employment", {})
    add = profile.get("additional_income", {})
    ded = profile.get("deductions", {})

    emp_type = (emp.get("employment_type") or "").lower()
    salary = float(emp.get("annual_salary") or 0)

    # 2. Salary documents
    if emp_type in ("salaried", "retired", "") and salary > 0:
        docs.extend(DOCUMENTS["salary"])

    # 3. Business / Self-employed / Freelance records
    if emp_type in ("business", "self_employed", "freelancer"):
        docs.extend(DOCUMENTS["business"])

    # 4. Home loan documents
    has_home_loan = ded.get("home_loan") is True or float(ded.get("home_loan_interest") or 0) > 0
    if has_home_loan:
        docs.extend(DOCUMENTS["home_loan"])

    # 5. Rent / HRA exemption documents
    has_rent = ded.get("hra_applicable") is True or float(ded.get("hra_amount") or 0) > 0
    if has_rent:
        docs.extend(DOCUMENTS["rent"])

    # 6. Investment proofs (80C, 80D, NPS)
    has_investments = (
        float(ded.get("section_80c") or 0) > 0
        or float(ded.get("health_insurance") or 0) > 0
        or float(ded.get("nps") or 0) > 0
    )
    if has_investments:
        docs.extend(DOCUMENTS["investments"])

    # 7. Capital gains documents
    has_cap_gains = add.get("capital_gains") is True or float(add.get("capital_gains_amount") or 0) > 0
    if has_cap_gains:
        docs.extend(DOCUMENTS["capital_gains"])

    # 8. House property / Rental income documents
    has_house_prop = add.get("rental_income") is True or float(add.get("rental_income_amount") or 0) > 0
    if has_house_prop:
        docs.extend(DOCUMENTS["house_property"])

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for d in docs:
        if d not in seen:
            seen.add(d)
            deduped.append(d)
    return deduped


# Services database (In-memory mock data for FastAPI backend)
Services = [
    {
        "id": "1",
        "key": "itr-filing",
        "name": "ITR Filing (Income Tax Return)",
        "description": "Income Tax Return Filing for Individuals and HUF",
        "Official_Link": "https://www.incometax.gov.in/",
        "documents_required": DOCUMENTS["common"] + DOCUMENTS["salary"],
        "optional_documents": ["Investment Proofs (80C)", "Rent Receipts / HRA", "Housing Loan Interest Certificate"],
        "guidance": [
            "Match salary details from Form 16 with Tax Information Statement (AIS / 26AS).",
            "Claim eligible deductions under Section 80C, 80D, and HRA.",
            "Choose optimal tax regime (Old vs New Tax Regime) for maximum savings.",
            "File and e-verify your return on the Income Tax Portal using Aadhaar OTP."
        ]
    },
    {
        "id": "2",
        "key": "new-pan",
        "name": "New PAN Application",
        "description": "New PAN Card Application for Individuals and HUF",
        "Official_Link": "https://www.incometax.gov.in/",
        "documents_required": ["Aadhaar Card", "Proof of Address", "Passport Size Photograph"],
        "optional_documents": ["Voter ID", "Birth Certificate"],
        "guidance": [
            "Fill Form 49A (for Indian Citizens) with exact details matching Aadhaar Card.",
            "Upload verified identity proof and address proof documents.",
            "Complete e-KYC using Aadhaar linked mobile number for instant e-PAN generation.",
            "Physical PAN Card will be dispatched to your registered postal address."
        ]
    }
]

def find_service(service_id: str, profile: Optional[Dict[str, Any]] = None):
    sid_lower = service_id.lower()
    for service in Services:
        srv_id = str(service.get("id", "")).lower()
        srv_key = str(service.get("key", "")).lower()
        srv_name = str(service.get("name", "")).lower()
        if sid_lower in (srv_id, srv_key, srv_key.replace("-", ""), srv_name):
            srv_copy = dict(service)
            if srv_key == "itr-filing" and profile:
                srv_copy["documents_required"] = get_itr_documents_for_profile(profile)
            return srv_copy
    return None

if not os.path.exists("react-tax-assistant/dist"):
    @app.get("/")
    def home():
        return {
            "status": "online",
            "message": "Welcome to Tax Assistant API",
            "endpoints": ["/services", "/services/{service_id}", "/{service_id}/roadmap", "/current-selection"]
        }


@app.get("/services")
def all_services(session_id: Optional[str] = None):
    profile = None
    if session_id and session_id in _chat_sessions:
        profile = _chat_sessions[session_id].get("profile")
    result = []
    for s in Services:
        service_id = s.get("key") or s.get("id")
        if isinstance(service_id, str):
            result.append(find_service(service_id, profile=profile))
    return result

@app.get("/current-selection")
def get_current_selection():
    return {
        "selected_service": selected_service,
        "user_documents": user_documents,
        "added_documents": added_documents
    }

@app.get("/services/{service_id}")
def get_service(service_id: str, session_id: Optional[str] = None):
    profile = None
    if session_id and session_id in _chat_sessions:
        profile = _chat_sessions[session_id].get("profile")
    service = find_service(service_id, profile=profile)
    if service:
        return service
    raise HTTPException(status_code=404, detail="Service not found")

@app.post("/{service_id}/roadmap")
@app.post("/services/{service_id}/roadmap")
def get_roadmap(service_id: str, payload: DocumentPayload, session_id: Optional[str] = None):
    profile = None
    if session_id and session_id in _chat_sessions:
        profile = _chat_sessions[session_id].get("profile")
    service = find_service(service_id, profile=profile)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Update active service and documents received from UI request
    srv_key = service.get("key", service_id)
    u_docs = payload.user_documents or []
    a_docs = payload.added_documents or []
    
    update_user_selection(service_id=str(srv_key), u_docs=u_docs, a_docs=a_docs)
    
    active_docs = u_docs if u_docs else a_docs
    
    # Import agent roadmap dynamically and generate roadmap using AI agent
    from agent import roadmap
    required_documents = service.get("documents_required")

    if isinstance(required_documents, str):
        required_documents = [required_documents]
    elif not isinstance(required_documents, list):
        required_documents = None

    return roadmap(
        str(srv_key),
        active_docs,
        required_documents=required_documents
    )


# =====================================================================
# CHAT SESSION STATE  (in-memory, keyed by session_id)
# Each session stores:
#   messages  – full conversation history  [{"role": ..., "content": ...}]
#   complete  – whether profile extraction is done
#   profile   – the extracted user profile dict (once complete)
# =====================================================================
_chat_sessions: Dict[str, Dict[str, Any]] = {}

# Minimum confirmed fields before we consider the profile "complete"
_REQUIRED_FIELDS = [
    "employment_type",
    "annual_salary",
    "capital_gains",
    "rental_income",
    "home_loan",
    "section_80c",
    "tax_regime_preference",
]

def _profile_is_complete(profile: Dict[str, Any]) -> bool:
    """
    Return True when every required top-level field and conditional amount detail is confirmed.
    If a user answers 'yes' to home_loan, rental_income, or capital_gains, their corresponding
    amount must also be confirmed before considering the profile complete.
    """
    flat = {
        **profile.get("employment", {}),
        **profile.get("additional_income", {}),
        **profile.get("deductions", {}),
        **profile.get("filing", {}),
    }
    # Check baseline required fields
    if not all(flat.get(f) is not None for f in _REQUIRED_FIELDS):
        return False

    # If user has a home loan, interest amount must be confirmed
    if flat.get("home_loan") is True and flat.get("home_loan_interest") is None:
        return False

    # If user has rental income, rental amount must be confirmed
    if flat.get("rental_income") is True and flat.get("rental_income_amount") is None:
        return False

    # If user has capital gains, capital gains amount must be confirmed
    if flat.get("capital_gains") is True and flat.get("capital_gains_amount") is None:
        return False

    return True


def _fill_profile_defaults(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fill any still-None required fields with safe defaults so the session
    can complete even if the chatbot didn't explicitly cover every field.
    Booleans default to False, numeric to 0, strings to 'undecided'.
    For business/self-employed users, if annual_salary is None but
    other_income is set, promote other_income to annual_salary.
    """
    # Promote other_income → annual_salary for non-salaried users before applying defaults
    emp = profile.get("employment", {})
    if emp.get("annual_salary") is None and emp.get("other_income") is not None:
        profile.setdefault("employment", {})["annual_salary"] = emp["other_income"]

    defaults = {
        "employment_type":       "salaried",
        "annual_salary":         0,
        "capital_gains":         False,
        "rental_income":         False,
        "home_loan":             False,
        "section_80c":           0,
        "tax_regime_preference": "undecided",
    }
    groups = {
        "employment":       ["employment_type", "annual_salary"],
        "additional_income":["capital_gains", "rental_income"],
        "deductions":       ["home_loan", "section_80c"],
        "filing":           ["tax_regime_preference"],
    }
    for group, fields in groups.items():
        for f in fields:
            if profile.get(group, {}).get(f) is None:
                profile.setdefault(group, {})[f] = defaults[f]

    # Fill conditional amounts if boolean is True but amount is None
    ded = profile.setdefault("deductions", {})
    if ded.get("home_loan") is True and ded.get("home_loan_interest") is None:
        ded["home_loan_interest"] = 0

    inc = profile.setdefault("additional_income", {})
    if inc.get("rental_income") is True and inc.get("rental_income_amount") is None:
        inc["rental_income_amount"] = 0
    if inc.get("capital_gains") is True and inc.get("capital_gains_amount") is None:
        inc["capital_gains_amount"] = 0

    return profile


def retrieve_information(session_id: str, user_message: str) -> Dict[str, Any]:
    """
    Core session manager for the chat-based profile collection flow.

    Steps
    -----
    1. Look up (or create) the in-memory session.
    2. Append the user's message to the history.
    3. Send the full history to the IncomeTaxChatbot (chat_agent) and get
       its next reply.
    4. Append the bot reply to the history.
    5. Run extract_user_profile_from_session to see what we know so far.
    6. If all required fields are filled, mark the session complete and
       return the final profile.  Otherwise return the bot's reply so the
       frontend can display it and ask the next question.

    Returns a dict compatible with ChatMessageResponse.
    """
    from chat_agent import extract_user_profile_from_session

    # --- 1. Session lookup / creation --------------------------------
    if session_id not in _chat_sessions:
        _chat_sessions[session_id] = {
            "messages": [],
            "complete": False,
            "profile": None,
        }
        log.info("🆕  New session created  [%s]", session_id[:8])

    session = _chat_sessions[session_id]
    turn = len([m for m in session["messages"] if m["role"] == "user"]) + 1

    # Already finished — just return cached result
    if session["complete"]:
        log.info("✅  Session [%s] already complete — returning cached profile", session_id[:8])
        return {
            "session_id": session_id,
            "reply": "We already have all the information we need. See your profile below.",
            "is_complete": True,
            "profile": session["profile"],
        }

    # --- 2. Append user message --------------------------------------
    log.info("💬  Turn %d | User: %s", turn, user_message[:120])
    session["messages"].append({"role": "user", "content": user_message})

    # --- 3. Call the chatbot -----------------------------------------
    log.info("🤖  Calling chat agent...")
    bot_reply = _run_chat_agent(session["messages"])
    log.info("🤖  Bot reply: %s", bot_reply[:120])

    # --- 4. Append bot reply -----------------------------------------
    session["messages"].append({"role": "assistant", "content": bot_reply})

    # --- 5. Extract what we know so far ------------------------------
    log.info("🔍  Extracting profile from %d messages...", len(session["messages"]))
    profile = extract_user_profile_from_session(session["messages"])

    # Log only non-None fields so it's readable
    flat = {
        **profile.get("employment", {}),
        **profile.get("additional_income", {}),
        **profile.get("deductions", {}),
        **profile.get("filing", {}),
    }
    collected = {k: v for k, v in flat.items() if v is not None}
    missing   = [f for f in _REQUIRED_FIELDS if flat.get(f) is None]

    log.info("📋  Collected (%d/%d required): %s",
             len([f for f in _REQUIRED_FIELDS if flat.get(f) is not None]),
             len(_REQUIRED_FIELDS),
             collected)
    if missing:
        log.info("⏳  Still waiting for: %s", missing)

    # --- 6. Decide if we're done -------------------------------------
    # Force-complete after 12 user turns to avoid indefinite loops —
    # fill any still-missing required fields with safe defaults first.
    user_turns = len([m for m in session["messages"] if m["role"] == "user"])
    if user_turns >= 12 and not _profile_is_complete(profile):
        log.info("⚡  Force-completing after %d turns — filling defaults for: %s", user_turns, missing)
        profile = _fill_profile_defaults(profile)

    complete = _profile_is_complete(profile)
    if complete:
        session["complete"] = True
        session["profile"] = profile
        log.info("Profile complete for session [%s]!", session_id[:8])

    return {
        "session_id": session_id,
        "reply": bot_reply,
        "is_complete": complete,
        "profile": profile if complete else None,
    }


def _run_chat_agent(messages: List[Dict[str, str]]) -> str:
    """
    Send the conversation history to the IncomeTaxChatbot and return its
    next reply as a plain string. Uses the new google-genai SDK with Chat.
    """
    from google import genai
    from google.genai import types
    from chat_agent import agent_system_instruction

    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY", ""))

    # Build prior history (everything except the last user message)
    history = []
    for msg in messages[:-1]:
        role = "model" if msg["role"] == "assistant" else "user"
        history.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

    chat = client.chats.create(
        model="gemini-flash-lite-latest",
        config=types.GenerateContentConfig(
            system_instruction=agent_system_instruction,
            tools=[search_tax_documents],
        ),
        history=history,
    )
    print("\n📨 Sending question to Gemini:", messages[-1]["content"], flush=True)
    response = chat.send_message(messages[-1]["content"])
    print("\n📦 Gemini response received", flush=True)
    print(response, flush=True)
    # Safely extract text; handle cases where response or response.text may be None
    reply = response.text if getattr(response, "text", None) else ""
    return reply.strip()


# =====================================================================
# CHAT ENDPOINTS
# =====================================================================

@app.post("/chat/message", response_model=ChatMessageResponse)
def chat_message(payload: ChatMessageRequest):
    """
    Send a message to the IncomeTaxChatbot.

    - On the first call, omit session_id (or send null) to start a new
      session. The assigned session_id is returned and must be sent back
      on every subsequent call to continue the same conversation.
    - When is_complete is True, the full extracted profile is included
      in the response and the session is considered finished.
    """
    sid = payload.session_id or str(uuid.uuid4())
    result = retrieve_information(sid, payload.message)
    return ChatMessageResponse(**result)


@app.get("/chat/profile/{session_id}")
def get_chat_profile(session_id: str) -> Dict[str, Any]:
    """
    Retrieve the extracted user profile for a completed chat session.
    Returns 404 if the session does not exist or 409 if not yet complete.
    """
    session = _chat_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session["complete"]:
        raise HTTPException(status_code=409, detail="Session not yet complete")
    return session["profile"]


@app.delete("/chat/session/{session_id}")
def clear_chat_session(session_id: str):
    """Reset a chat session so the user can start over."""
    _chat_sessions.pop(session_id, None)
    return {"status": "cleared", "session_id": session_id}


# =====================================================================
# TAX REPORT ENDPOINT
# =====================================================================

@app.get("/tax-report/{session_id}")
def get_tax_report(session_id: str) -> Dict[str, Any]:
    """
    Generate a full tax report for a completed chat session.
    Calls regime_calculator with the session's extracted user profile
    and returns old vs new regime comparison + recommendation.
    Returns 404 if session not found, 409 if not yet complete.
    """
    session = _chat_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session["complete"] or not session["profile"]:
        raise HTTPException(status_code=409, detail="Session not yet complete")

    from agent import regime_calculator
    report = regime_calculator(session["profile"])
    req_docs = get_itr_documents_for_profile(session["profile"])
    report["required_documents"] = req_docs
    return {
        "session_id": session_id,
        "user_profile": session["profile"],
        "tax_report": report,
        "required_documents": req_docs,
    }


# =====================================================================
# ASK ABOUT THE REPORT  — contextual mini-chat
# =====================================================================

class AskReportRequest(BaseModel):
    session_id: str          # must be a completed session
    question: str            # user's free-text question about their report
    history: List[Dict[str, str]] = []  # prior Q&A turns [{role, content}]


@app.post("/ask-report")
def ask_about_report(payload: AskReportRequest) -> Dict[str, Any]:
    """
    Answer a user's question about their personal tax report.

    The Gemini model receives the full tax report JSON + user profile
    as system context, so it can answer questions like:
      - "Why is my old regime tax lower?"
      - "What documents do I need for 80C?"
      - "How much can I save if I add NPS?"

    Maintains a short multi-turn history supplied by the frontend.
    """
    session = _chat_sessions.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session["complete"] or not session["profile"]:
        raise HTTPException(status_code=409, detail="Session not yet complete")

    from agent import regime_calculator
    from google import genai
    from google.genai import types
    import json as _json

    # Build the tax report for context
    report = regime_calculator(session["profile"])
    profile = session["profile"]

    system_ctx = f"""You are a helpful Indian income tax advisor.
The user has completed a tax profiling conversation and received a
personalised tax report. Use ONLY the data below to answer their
questions. Be concise, friendly, and specific — always refer to the
actual numbers from their report. Do not invent rules or figures.

=== USER PROFILE ===
{_json.dumps(profile, indent=2)}

=== TAX REPORT ===
{_json.dumps(report, indent=2)}

Guidelines:
- Quote actual numbers from the report (e.g. "Your Old Regime tax is ₹30,680").
- If asked about deductions, explain which section they fall under.
- If asked to compare, show both figures side by side.
- If a question is outside the scope of the report, say so clearly and
  suggest checking the official Income Tax Department portal.
- Keep answers to 3-5 sentences unless a detailed breakdown is requested.
- Format amounts as ₹X,XX,XXX using Indian numbering.
"""

    # Build conversation history for multi-turn context
    history = []
    for msg in payload.history:
        role = "model" if msg["role"] == "assistant" else "user"
        history.append(
            types.Content(role=role, parts=[types.Part(text=msg["content"])])
        )

    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY", ""))
    chat = client.chats.create(
        model="gemini-flash-lite-latest",
        config=types.GenerateContentConfig(system_instruction=system_ctx),
        history=history,
    )
    response = chat.send_message(payload.question)
    answer = response.text if getattr(response, "text", None) else ""

    log.info("💡  Ask-report | Q: %s | A: %s", payload.question[:80], answer[:80])

    return {
        "question": payload.question,
        "answer": answer,
    }


from fastapi.staticfiles import StaticFiles

# Mount React static files (after all API routes have been defined)
if os.path.exists("react-tax-assistant/dist"):
    app.mount("/", StaticFiles(directory="react-tax-assistant/dist", html=True), name="static")

