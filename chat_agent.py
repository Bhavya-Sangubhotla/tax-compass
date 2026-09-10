import os
import re
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from google.adk import Agent
from agent import get_processes, roadmap, subprocess_roadmap, video_fetcher
from tax_search import search_tax_documents

load_dotenv()

def search_tax_documents_with_query(query: str, document_type: str | None = None) -> Dict[str, Any]:
    """
    Placeholder function — searches official tax documents, circulars,
    and notifications relevant to the user's query.

    Parameters
    ----------
    query : str
        The search term or question (e.g. "HRA exemption rules",
        "Section 80C limit FY 2024-25").
    document_type : str | None
        Optional filter — "circular" | "notification" | "form" |
        "act" | "rule" | None (search all).

    Returns
    -------
    dict with keys:
        query          – echoed search query
        document_type  – echoed filter
        results        – list of matching document stubs
        status         – "placeholder" (will be "ok" once implemented)

    TODO: Replace with a real search against the Income Tax Department
    document index (https://www.incometax.gov.in) or a local vector
    store of official circulars, forms, and acts.
    """
    return {
        "query": query,
        "document_type": document_type,
        "results": [],
        "status": "placeholder",
        "message": (
            f"search_tax_documents('{query}') is not yet implemented. "
            "Wire this function to a real document search backend to "
            "return relevant Income Tax Department circulars, forms, "
            "and notifications."
        ),
    }

agent_system_instruction = ("""
You are IncomeTaxChatbot, a helpful conversational assistant for
Indian taxpayers.

Your purpose is to understand the user's individual situation and
help them navigate Income Tax Department services in a clear,
simple, and structured way.

IMPORTANT:

1. OFFICIAL SOURCES

Use official Income Tax Department and Government of India
documentation as your primary source of truth.

Official sources should take precedence over general knowledge.

Do not invent:
- tax rules
- eligibility criteria
- document requirements
- deadlines
- government URLs
- filing procedures
- tax rates
- deductions
- ITR applicability

If reliable information is unavailable, clearly say that you are
not certain and recommend checking the latest official Income Tax
Department guidance.

2. UNDERSTAND THE USER'S SITUATION

Users may describe their situation naturally.

For example:

"I'm a salaried employee earning around 12 LPA and I want to
file my ITR."

Extract useful information from what the user tells you, such as:

- employment type
- income
- sources of income
- investments
- deductions
- house/property income
- capital gains
- previous filing information
- other relevant circumstances

Do not ask the user for information they have already provided.

3. COLLECT REQUIRED PROFILE FIELDS

You MUST collect the following fields through the conversation
before considering it complete. Ask about any that are missing:

  a) Employment type (salaried / self-employed / business / retired)
  b) Annual income / salary amount
  c) Capital gains — yes or no (and approximate amount if yes)
  d) Rental income — yes or no (and approximate annual amount if yes)
  e) Home loan — yes or no (and annual interest amount if yes)
  f) Section 80C investments amount (PPF, ELSS, LIC etc.) — 0 if none
  g) Tax regime preference — old, new, or undecided

CRITICAL FOLLOW-UP RULES FOR "YES" ANSWERS:
- If the user says "yes" or confirms they have a HOME LOAN, but did NOT state the interest amount, DO NOT move to another question or conclude. You MUST immediately ask: "How much annual interest do you pay on your home loan?" (since Section 24b allows up to ₹2,00,000 deduction under the Old Regime).
- If the user says "yes" or confirms they have RENTAL INCOME, but did NOT state the amount, you MUST ask for the approximate annual rental income.
- If the user says "yes" or confirms they have CAPITAL GAINS, but did NOT state the amount, you MUST ask for the approximate capital gains amount.
- Never conclude or wrap up until these specific amounts are collected (or the user clarifies they don't know).

Do NOT ask all 7 topics at once. Ask 1-2 at a time naturally.
Once all required fields (and their amounts) are confirmed, wrap up with a brief summary.

4. ASK PROGRESSIVE QUESTIONS

Do not overwhelm the user with a large questionnaire.

Ask only the next most useful question based on what you already
know.

For example:

User:
"I'm a salaried employee earning 12 LPA."

Assistant:
"Got it. Do you have any income apart from your salary, such as
bank interest, rental income, dividends, or capital gains?"

Continue the conversation based on the user's answers.

4. HELP THE USER MAKE DECISIONS

Do not simply give the user a list of procedures.

Help them understand what applies to their situation.

For example, if the user wants to file an ITR, help determine:

- what type of ITR may be applicable
- what information is relevant
- what documents they may need
- whether additional information is required
- what their next steps should be

When making a recommendation, explain WHY it appears applicable.

Do not present a preliminary assessment as a guaranteed answer.

5. OLD VS NEW TAX REGIME

If the user asks about the old and new tax regimes, first
understand the user's financial situation.

Relevant information may include:

- salary income
- other income
- HRA
- home loan
- eligible investments
- health insurance
- NPS
- other potentially applicable deductions

Do not make assumptions when important information is missing.

6. DOCUMENTS

When discussing documents, distinguish between documents that are
definitely required and documents that may be applicable depending
on the user's situation.

Explain why an important document may be needed.

7. EXPLAIN TAX CONCEPTS SIMPLY

Avoid unnecessary tax jargon.

If you use a tax term, explain it in simple language.

The user should feel that they are talking to someone helping them
navigate the process, not reading a tax manual.

8. HANDLE UNCERTAINTY

Tax rules and government procedures can change.

If you are uncertain or the user's situation is unusual:

- clearly state what you know
- identify what is uncertain
- ask for the missing information
- recommend verification against the latest official source

Never fabricate an answer simply to keep the conversation moving.

9. CONVERSATION STYLE

Be friendly, clear and concise.

Do not overwhelm the user with information.

Ask one or a few relevant questions at a time.

Adapt your next question based on the user's previous answer.

10. IMPORTANT DISCLAIMER

You provide informational guidance only.

You are not a substitute for the official Income Tax Department
portal, official documentation, or professional tax advice.

Users should verify important filing decisions and the final
information against the latest official Income Tax Department
guidance.

11. FINAL PROMPT

Do not end the session with a question once the profile is collected.
It should be a conclusion explaining the user situation
and breif of what is applicable to the user.

Only end the session only after the entire details in the profile
are collection

For Example, if user says Yes to rental income or any other incomes
, DO NOT DEFAULT THE VALUES. ASK THE USER ABOUT THE INCOME OR THE OTHER 
QUESTIONS TO BUILD THE PROFILE.

12. STYLING

DO not use unnecessary special charatcters to coney sections in the reply prompt.
Use Bold styling to set apart heading and other information
use appropriate paragraph spacing to be the content readable.

MPORTANT SOURCE OF TRUTH:

The application has an official tax-document knowledge base stored in
BigQuery.

The `search_tax_documents` tool searches this knowledge base using
semantic search over the official Income Tax Department documents.

When answering questions that require specific information from
official tax documents, use `search_tax_documents` rather than relying
only on your general model knowledge.

The retrieved document information should be treated as the primary
source of truth for document-specific questions.

YOUR PRIMARY GOAL:

Understand the user's situation
        ↓
Collect all 7 required profile fields (see point 3)
        ↓
Ask the right follow-up questions
        ↓
Determine what applies to the user
        ↓
Explain why
        ↓
Guide the user toward the appropriate next step
"""
)

chat_agent = Agent(
    name="IncomeTaxChatbot",
    model="gemini-2.5-flash",
    description="Conversational assistant that understands an Indian taxpayer's "
        "situation and guides them through relevant Income Tax Department "
        "processes",
    instruction=agent_system_instruction,
    tools=[get_processes, roadmap, subprocess_roadmap, video_fetcher,search_tax_documents, search_tax_documents_with_query]
)

def get_main_selection():
    """Reads the service selected and user or added documents from main.py (populated from UI)."""
    import main
    svc = getattr(main, "selected_service", "itr-filing")
    u_docs = getattr(main, "user_documents", [])
    a_docs = getattr(main, "added_documents", [])
    docs = u_docs if u_docs else a_docs
    return svc, docs




# =====================================================================
# USER PROFILE BUILDER
# =====================================================================

def build_user_profile(
    # --- Employment & Income ---
    employment_type: str | None = None,          # "salaried" | "self_employed" | "business" | "freelancer" | "retired" | "other"
    annual_salary: float | None = None,           # Gross salary / CTC in INR
    other_income: float | None = None,            # Interest, dividends, freelance, etc. in INR

    # --- Additional Income Sources ---
    capital_gains: bool | None = None,            # Any short-term or long-term capital gains
    capital_gains_amount: float | None = None,    # Approximate amount in INR
    rental_income: bool | None = None,            # Rental income from property
    rental_income_amount: float | None = None,    # Approximate annual rental income in INR
    interest_income: float | None = None,         # Bank/FD/savings account interest in INR
    dividend_income: float | None = None,         # Dividend income from shares/MFs in INR
    freelance_income: float | None = None,        # Freelance/consulting income (if not primary) in INR
    agriculture_income: float | None = None,      # Agricultural income in INR (exempt but affects slab)
    foreign_income: float | None = None,          # Foreign income / DTAA-covered income in INR

    # --- Deductions & Investments ---
    home_loan: bool | None = None,                # Has an active home loan (principal + interest deduction)
    home_loan_interest: float | None = None,      # Annual home loan interest paid in INR (Sec 24b)
    section_80c: float | None = None,             # Total 80C investments in INR (PPF, ELSS, LIC, etc.)
    health_insurance: float | None = None,        # 80D premium paid in INR
    nps: float | None = None,                     # NPS contribution in INR (80CCD(1B))
    hra_applicable: bool | None = None,           # Receives HRA as part of salary
    hra_amount: float | None = None,              # Annual HRA received in INR

    # --- Tax Regime & Filing ---
    tax_regime_preference: str | None = None,     # "old" | "new" | "undecided"
    previous_itr_filed: bool | None = None,       # Has filed ITR before
    itr_type: str | None = None,                  # Likely applicable ITR form e.g. "ITR-1", "ITR-4"

    # --- Available Documents ---
    available_documents: list[str] | None = None, # Documents user has on hand

    # --- Meta ---
    situation_summary: str | None = None,         # Free-text summary of the user's situation
) -> dict:
    """
    Returns a structured JSON-serialisable dict of everything the
    chatbot has learned about the user.  All fields default to None
    so that only confirmed information is included; callers can
    filter out None values if a compact payload is needed.
    """
    return {
        "employment": {
            "employment_type": employment_type,
            "annual_salary": annual_salary,
            "other_income": other_income,
        },
        "additional_income": {
            "capital_gains": capital_gains,
            "capital_gains_amount": capital_gains_amount,
            "rental_income": rental_income,
            "rental_income_amount": rental_income_amount,
            "interest_income": interest_income,
            "dividend_income": dividend_income,
            "freelance_income": freelance_income,
            "agriculture_income": agriculture_income,
            "foreign_income": foreign_income,
        },
        "deductions": {
            "home_loan": home_loan,
            "home_loan_interest": home_loan_interest,
            "section_80c": section_80c,
            "health_insurance": health_insurance,
            "nps": nps,
            "hra_applicable": hra_applicable,
            "hra_amount": hra_amount,
        },
        "filing": {
            "tax_regime_preference": tax_regime_preference,
            "previous_itr_filed": previous_itr_filed,
            "itr_type": itr_type,
        },
        "available_documents": available_documents or [],
        "situation_summary": situation_summary,
    }


def extract_user_profile_from_session(
    session_messages: List[Dict[str, str]],
) -> dict:
    """
    Parses a list of chat messages from the IncomeTaxChatbot session and
    returns a populated user profile dict built via `build_user_profile`.

    Each message in `session_messages` should be a dict with:
        {"role": "user" | "assistant", "content": "<text>"}

    The function calls the same Gemini model used by the chatbot and
    asks it to extract every piece of confirmed information from the
    conversation, then maps the result into `build_user_profile`.

    Returns the profile dict on success, or a dict with an "error" key
    on failure.
    """
    if not session_messages:
        return build_user_profile()

    # Build a plain-text transcript for the extraction prompt
    transcript_lines = []
    for msg in session_messages:
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "").strip()
        if content:
            transcript_lines.append(f"{role}: {content}")
    transcript = "\n".join(transcript_lines)

    extraction_prompt = f"""
You are a precise data extraction assistant for Indian income tax profiles.

Below is a conversation between a user and an Indian income tax chatbot.
Read it carefully and extract ONLY information that the user has explicitly
stated or clearly confirmed. Do NOT infer values that were not mentioned.

Return a single valid JSON object with exactly these keys (use null for any
field that was not mentioned or confirmed):

{{
  "employment_type":         null,   // "salaried"|"self_employed"|"business"|"freelancer"|"retired"|"other"
  "annual_salary":           null,   // TOTAL annual income in INR — includes salary, business profit, professional income, or freelance earnings. Convert LPA: 1 LPA = 100000 INR. If user mentions turnover, use profit/net income if stated, else use turnover.
  "other_income":            null,   // Other income in INR (interest, dividends — NOT the main salary/business income)
  "capital_gains":           null,   // true | false
  "capital_gains_amount":    null,   // number in INR
  "rental_income":           null,   // true | false
  "rental_income_amount":    null,   // number in INR
  "home_loan":               null,   // true | false
  "home_loan_interest":      null,   // number in INR
  "section_80c":             null,   // number in INR — if user says "no investments", "none", "I don't invest", or "not applicable", set to 0 (not null)
  "health_insurance":        null,   // number in INR (80D premium)
  "nps":                     null,   // number in INR (80CCD(1B))
  "hra_applicable":          null,   // true | false
  "hra_amount":              null,   // number in INR
  "tax_regime_preference":   null,   // "old"|"new"|"undecided" — if user says "not sure", "unsure", "don't know", "you decide", "not applicable", or "doesn't matter", set to "undecided" (not null)
  "previous_itr_filed":      null,   // true | false
  "itr_type":                null,   // e.g. "ITR-1", "ITR-3", "ITR-4"
  "available_documents":     null,   // list of strings, e.g. ["Form 16","PAN Card"]
  "situation_summary":       null    // one or two sentence plain-English summary of the user's situation
}}

Rules:
- Return ONLY the raw JSON object — no markdown fences, no explanation.
- Convert LPA to INR (1 LPA = 100000 INR).
- For business/self-employed users: map business profit, professional income, or net earnings to "annual_salary".
- If the user says "yes" or confirms a home loan: set "home_loan": true. If they have NOT mentioned the annual interest amount, set "home_loan_interest": null. Only set "home_loan_interest" to a number if explicitly stated, or 0 if they explicitly say no interest or don't know.
- If the user says "no" or "I don't have" to home loan: set "home_loan": false and "home_loan_interest": 0.
- If the user says "yes" to rental income: set "rental_income": true. If amount is not given yet, set "rental_income_amount": null.
- If the user says "no" to rental income: set "rental_income": false and "rental_income_amount": 0.
- If the user says "yes" to capital gains: set "capital_gains": true. If amount is not given yet, set "capital_gains_amount": null.
- If the user says "no" to capital gains: set "capital_gains": false and "capital_gains_amount": 0.
- For section_80c: if user explicitly says no investments or none, set to 0. Only use null if the topic was never discussed.
- For tax_regime_preference: "not sure" / "unsure" / "don't know" = "undecided". Only use null if never discussed.

Conversation:
{transcript}
"""
    raw = ""

    try:
        from google import genai

        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY", ""))
        response = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=extraction_prompt,
        )
   
        raw = (response.text or "").strip()

        # Strip markdown fences if the model wrapped the JSON anyway
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        extracted: dict = json.loads(raw)

        return build_user_profile(
            employment_type=extracted.get("employment_type"),
            annual_salary=extracted.get("annual_salary"),
            other_income=extracted.get("other_income"),
            capital_gains=extracted.get("capital_gains"),
            capital_gains_amount=extracted.get("capital_gains_amount"),
            rental_income=extracted.get("rental_income"),
            rental_income_amount=extracted.get("rental_income_amount"),
            home_loan=extracted.get("home_loan"),
            home_loan_interest=extracted.get("home_loan_interest"),
            section_80c=extracted.get("section_80c"),
            health_insurance=extracted.get("health_insurance"),
            nps=extracted.get("nps"),
            hra_applicable=extracted.get("hra_applicable"),
            hra_amount=extracted.get("hra_amount"),
            tax_regime_preference=extracted.get("tax_regime_preference"),
            previous_itr_filed=extracted.get("previous_itr_filed"),
            itr_type=extracted.get("itr_type"),
            available_documents=extracted.get("available_documents"),
            situation_summary=extracted.get("situation_summary"),
        )

    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse model response as JSON: {e}", "raw_response": raw}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    print("=" * 70)
    print(f"🤖 Agent Initialized: {chat_agent.name}")
    print(f"📦 Framework: Google Agent Development Kit (google-adk v2.7.0)")
    print(f"🧠 Model: {chat_agent.model}")
    print("=" * 70)