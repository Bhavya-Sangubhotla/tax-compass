import os
import re
import json
import urllib.request
import urllib.parse
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional
from google.adk import Agent
from tax_search import search_tax_documents


# =====================================================================
# AGENT TOOL DEFINITIONS
# =====================================================================

def get_processes() -> List[Dict[str, Any]]:
    """Fetches all supported Income Tax Portal services, official links, and document requirements."""
    return [
        {
            "process_id": "itr-filing",
            "name": "Income Tax Return (ITR-1 / ITR-4) Filing",
            "official_url": "https://www.incometax.gov.in/iec/foportal/",
            "description": "Annual income tax return filing for salaried individuals, HUFs, and small business owners.",
            "required_documents": ["Form 26AS", "AIS", "Bank Statements", "Form 16", "Form 16A", "Pay Slips"],
            "optional_documents": ["Investment / Premium Payment Receipts", "Rent Receipts / Rental Agreement", "Housing Loan Interest Certificate", "Capital Gains Statement"]
        },
        {
            "process_id": "new-pan",
            "name": "New PAN Application / Instant e-PAN",
            "official_url": "https://eportal.incometax.gov.in/iec/foservices/#/pre-login/instant-e-pan",
            "description": "Instant e-PAN allocation via Aadhaar e-KYC or physical PAN card application via Form 49A.",
            "required_documents": ["Aadhaar Card", "Proof of Address", "Passport Size Photograph"],
            "optional_documents": ["Voter ID", "Birth Certificate"]
        },
        {
            "process_id": "everify-return",
            "name": "e-Verify Income Tax Return",
            "official_url": "https://eportal.incometax.gov.in/iec/foservices/#/pre-login/e-verify",
            "description": "e-Verification of filed ITR within 30 days using Aadhaar OTP, Net Banking, or EVC.",
            "required_documents": ["Aadhaar Card (Mobile Linked)", "Bank Account (EVC Enabled)", "ITR-V Acknowledgement"],
            "optional_documents": ["Demat Account"]
        },
        {
            "process_id": "ais-tis-download",
            "name": "Download AIS / TIS & Form 26AS",
            "official_url": "https://www.incometax.gov.in/iec/foportal/",
            "description": "Access Annual Information Statement (AIS) and Tax Information Summary (TIS) for tax credits.",
            "required_documents": ["PAN Card", "Income Tax Portal Credentials"],
            "optional_documents": ["Aadhaar OTP"]
        }
    ]

def roadmap(process_id: str, available_documents: List[str], required_documents: Optional[List[str]] = None) -> Dict[str, Any]:
    """Generates a customized, easy path to complete the selected Income Tax process based on available documents."""
    processes = get_processes()
    matched_process = next((p for p in processes if p["process_id"] == process_id or process_id.lower() in p["name"].lower()), None)
    
    if not matched_process:
        matched_process = processes[0]  # Default to ITR filing

    if required_documents:
        req_docs = list(required_documents)
    else:
        req_docs = matched_process["required_documents"]

    avail_lower = [d.strip().lower() for d in available_documents if d.strip()]

    missing_docs = []
    for req in req_docs:
        req_lower = req.lower()
        if not any(a in req_lower or req_lower in a for a in avail_lower):
            missing_docs.append(req)

    is_ready = len(missing_docs) == 0

    steps = []
    sub_guides = []
    if is_ready:
        steps = [
            f"1. Visit the official portal: {matched_process['official_url']}",
            "2. Log in using your PAN / Aadhaar credentials.",
            "3. Verify pre-filled salary & TDS information against Form 26AS / AIS.",
            "4. Compute total income, claim eligible deductions (80C, 80D, HRA), and choose Old vs New Tax Regime.",
            "5. Submit return and perform instant e-Verification via Aadhaar OTP."
        ]
    else:
        steps = [
            f"1. Document status: You currently have {len(req_docs) - len(missing_docs)} of {len(req_docs)} required documents.",
            f"2. Outstanding missing documents: {', '.join(missing_docs)}."
        ]

        # Execute subprocess_roadmap to acquire missing document guidance
        sub_roadmap = subprocess_roadmap(missing_docs)
        sub_guides = sub_roadmap.get("acquisition_roadmap", [])

        step_counter = 3
        for guide in sub_guides:
            steps.append(
                f"{step_counter}. How to acquire {guide['document']}: {guide['steps']} (Source: {guide['source']})"
            )
            step_counter += 1

        steps.append(
            f"{step_counter}. Once all missing documents are acquired, log into {matched_process['official_url']} to finish filing."
        )

    # Dynamically fetch real video tutorials based on process name and missing documents
    vids = video_fetcher(query=matched_process['name'], missing_documents=missing_docs)

    return {
        "process_name": matched_process["name"],
        "official_url": matched_process["official_url"],
        "available_documents": available_documents,
        "required_documents": req_docs,
        "missing_documents": missing_docs,
        "ready_to_proceed": is_ready,
        "acquisition_roadmap": sub_guides,
        "tutorial_videos": vids,
        "completion_path": steps,
        "guidance": steps
    }

def subprocess_roadmap(missing_documents: List[str]) -> Dict[str, List[Dict[str, str]]]:
    """Provides reliable, detailed step-by-step instructions on how to obtain missing tax documents."""
    guides = []
    
    for doc in missing_documents:
        doc_lower = doc.lower()
        if "form 16a" in doc_lower:
            guides.append({
                "document": "Form 16A",
                "source": "Bank / Deductor / TRACES Portal (https://www.tdscpc.gov.in/)",
                "steps": "Download Form 16A from your bank's net banking portal (TDS on FD interest) or request from clients/deductors who deducted TDS u/s 194J/194C."
            })
        elif "form 16" in doc_lower:
            guides.append({
                "document": "Form 16",
                "source": "Employer / TRACES Portal (https://www.tdscpc.gov.in/)",
                "steps": "Contact your HR/Payroll team or log into your employer portal. Employers issue Form 16 Part A (TRACES certified: https://www.tdscpc.gov.in/) and Part B by June 15 following the financial year."
            })
        elif "pay slip" in doc_lower or "payslip" in doc_lower:
            guides.append({
                "document": "Pay Slips",
                "source": "Employer HR Portal / ESS",
                "steps": "Download monthly salary slips (Apr to Mar) from your employer's HR/Payroll self-service portal to verify allowances and deductions."
            })
        elif "housing loan" in doc_lower or "home loan" in doc_lower:
            guides.append({
                "document": "Housing Loan Interest Certificate",
                "source": "Lender Net Banking Portal / Bank Branch",
                "steps": "Log into your home loan provider portal (e.g. SBI, HDFC, ICICI, LIC HFL) -> Home Loan Services -> Download Provisional / Final Interest Certificate for the financial year (Sec 24b & 80C principal)."
            })
        elif "rent receipt" in doc_lower or "rental agreement" in doc_lower:
            guides.append({
                "document": "Rent Receipts / Rental Agreement",
                "source": "Landlord / House Rental Contract",
                "steps": "Collect stamped rent receipts from landlord for each month. If annual rent exceeds ₹1,00,000, obtain landlord's PAN to claim HRA exemption under Sec 10(13A)."
            })
        elif "investment" in doc_lower or "premium" in doc_lower:
            guides.append({
                "document": "Investment / Premium Payment Receipts",
                "source": "Insurance / Mutual Fund / PPF Portals",
                "steps": "Download annual tax statements from insurance providers (LIC, HDFC Life), ELSS mutual fund tax certificates via CAMS/KFintech, and PPF/NPS account statements."
            })
        elif "capital gains" in doc_lower or "broker" in doc_lower:
            guides.append({
                "document": "Capital Gains Statement",
                "source": "Broker Portal (Zerodha / Groww / Upstox / CAMS)",
                "steps": "Log into your stock broker (e.g. Zerodha Console -> Reports -> Tax P&L, Groww -> Reports -> Capital Gains) and download the FY Capital Gains statement with STCG/LTCG breakdown."
            })
        elif "business" in doc_lower or "expense" in doc_lower or "profit & loss" in doc_lower or "financial" in doc_lower:
            guides.append({
                "document": "Business Income & Expense Records",
                "source": "Accounting Software (Tally / Zoho) / Bank Statements",
                "steps": "Compile profit & loss summary, sales registers, GST return summaries (GSTR-3B/GSTR-1), and bank statements reflecting business turnover and allowable expenses."
            })
        elif "tenant" in doc_lower or "municipal" in doc_lower:
            guides.append({
                "document": "House Property & Municipal Tax Details",
                "source": "Municipal Corporation Portal / Rental Account",
                "steps": "Collect municipal property tax payment receipts for deduction against house property rental income under Section 24."
            })
        elif "26as" in doc_lower or "ais" in doc_lower:
            guides.append({
                "document": "Form 26AS / AIS",
                "source": "Income Tax e-Filing Portal (https://www.incometax.gov.in/)",
                "steps": "Log into Income Tax Portal (https://www.incometax.gov.in/) -> e-File -> Income Tax Returns -> View Form 26AS or click 'AIS' tab to view and download annual tax information statement."
            })
        elif "bank statement" in doc_lower:
            guides.append({
                "document": "Bank Statements",
                "source": "Net Banking / Bank Mobile App",
                "steps": "Log into your bank's net banking app -> Account Statements -> Select Date Range (Apr 1 to Mar 31) -> Download PDF format."
            })
        elif "pan" in doc_lower:
            guides.append({
                "document": "PAN Card / e-PAN",
                "source": "Income Tax Instant e-PAN Portal (https://eportal.incometax.gov.in/)",
                "steps": "Visit https://eportal.incometax.gov.in/ -> Services -> Instant e-PAN. Enter Aadhaar number and perform OTP verification to download e-PAN instantly."
            })
        elif "aadhaar" in doc_lower:
            guides.append({
                "document": "Aadhaar Card",
                "source": "UIDAI Official Portal (https://myaadhaar.uidai.gov.in/)",
                "steps": "Visit https://myaadhaar.uidai.gov.in/ -> Download Aadhaar -> Enter Aadhaar No / Enrolment ID -> Enter OTP received on registered mobile number."
            })
        else:
            guides.append({
                "document": doc,
                "source": "Official Portal / Issuing Authority",
                "steps": f"Obtain {doc} from the relevant issuing authority or upload verified copy to proceed."
            })

    return {"acquisition_roadmap": guides}

def search_youtube_videos(search_query: str) -> List[Dict[str, Any]]:
    """Helper function to fetch live YouTube video search results."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(search_query)}"
    req = urllib.request.Request(url, headers=headers)
    results = []
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode('utf-8')
            match = re.search(r'var ytInitialData = ({.*?});</script>', html)
            if match:
                data = json.loads(match.group(1))
                sections = data.get("contents", {}).get("twoColumnSearchResultsRenderer", {}).get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", [])
                for section in sections:
                    items = section.get("itemSectionRenderer", {}).get("contents", [])
                    for item in items:
                        v = item.get("videoRenderer")
                        if v and "videoId" in v:
                            video_id = v["videoId"]
                            title = v.get("title", {}).get("runs", [{}])[0].get("text", "")
                            channel = v.get("ownerText", {}).get("runs", [{}])[0].get("text", "YouTube Creator")
                            results.append({
                                "title": title,
                                "channel": channel,
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "video_id": video_id
                            })
    except Exception as e:
        print(f"[YouTube Search] Query error for '{search_query}': {e}")
    return results

def title_similarity(target_title: str, video_title: str) -> float:
    """Calculates title similarity percentage between target title/query and YouTube video title."""
    if not target_title or not video_title:
        return 0.0
    seq_ratio = SequenceMatcher(None, target_title.lower(), video_title.lower()).ratio()
    target_words = set(re.findall(r'\w+', target_title.lower()))
    video_words = set(re.findall(r'\w+', video_title.lower()))
    if not target_words:
        return seq_ratio
    overlap_ratio = len(target_words.intersection(video_words)) / float(len(target_words))
    return max(seq_ratio, overlap_ratio)

def video_fetcher(query: str = "", missing_documents: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Fetches real YouTube tutorial video links. 
    If missing_documents is empty, returns 5 main process videos.
    Otherwise, returns (5 - len(missing_documents)) main process videos plus 1 video per missing document ('how to get {doc} in english').
    """
    if not query:
        svc, docs = get_main_selection()
        query = f"how to file {svc} online"

    if missing_documents is None:
        missing_documents = []

    matched_videos = []

    # 1. Calculate number of main process videos to fetch
    num_main_videos = 5 if not missing_documents else max(0, 5 - len(missing_documents))

    if num_main_videos > 0:
        # Search YouTube using main process query
        search_results = search_youtube_videos(query)

        # Filter videos matching >= 75% title similarity
        for vid in search_results:
            sim = title_similarity(query, vid["title"])
            if sim >= 0.75:
                matched_videos.append(vid)

        # If not enough videos passed 75% match, fill from top search results
        if len(matched_videos) < num_main_videos:
            existing_urls = {v["url"] for v in matched_videos}
            for vid in search_results:
                if vid["url"] not in existing_urls:
                    matched_videos.append(vid)
                    existing_urls.add(vid["url"])
                    if len(matched_videos) >= num_main_videos:
                        break

        matched_videos = matched_videos[:num_main_videos]

    # 2. Fetch first video for each missing document ("how to get {doc} in english")
    existing_urls = {v["url"] for v in matched_videos}
    for doc in missing_documents:
        doc_query = f"how to get {doc} in english"
        doc_videos = search_youtube_videos(doc_query)
        for v in doc_videos:
            if v["url"] not in existing_urls:
                matched_videos.append(v)
                existing_urls.add(v["url"])
                break  # Select top match per missing document

    return matched_videos

# =====================================================================
# AGENT DEFINITION WITH DETAILED SYSTEM INSTRUCTIONS
# =====================================================================

Extracted_information = []

agent_system_instruction = (
    """
You are IncomeTaxPortalAgent, an authoritative, read-only AI assistant
specializing in the official Indian Income Tax e-Filing Portal and
official Income Tax Department processes.

Your primary purpose is to understand the user's request, identify the
appropriate Income Tax Department process, retrieve reliable official
information when necessary, and guide the user toward the correct next
step.

IMPORTANT SOURCE OF TRUTH:

The application has an official tax-document knowledge base stored in
BigQuery.

The `search_tax_documents` tool searches this knowledge base using
semantic search over the official Income Tax Department documents.

When answering questions that require specific information from
official tax documents, use `search_tax_documents` rather than relying
only on your general model knowledge.

The retrieved document information should be treated as the primary
source of truth for document-specific questions.

--------------------------------------------------
CRITICAL CONSTRAINTS & BEHAVIOR
--------------------------------------------------

1. READ-ONLY GUARANTEE

You perform purely read-only information retrieval and guidance.

You NEVER:
- submit an income tax return
- modify a user's tax information
- modify government records
- perform transactions
- make changes on the official Income Tax portal
- claim that an action has been completed when you have only provided
  instructions

You may explain how a user can perform an action themselves.

--------------------------------------------------

2. OFFICIAL INFORMATION & RELIABILITY

For questions concerning official Income Tax Department rules,
procedures, forms, eligibility, filing requirements, documentation,
validation rules, or portal processes:

Use `search_tax_documents` to retrieve relevant official documentation
when the required information is available in the knowledge base.

Do not invent:
- tax rules
- eligibility criteria
- document requirements
- deadlines
- tax rates
- deductions
- ITR applicability
- filing procedures
- government URLs

Do not present uncertain information as a confirmed official rule.

If the retrieved official documents do not contain enough information
to answer confidently, clearly state the limitation and recommend
verification against the latest official Income Tax Department guidance.

--------------------------------------------------

3. DOCUMENT RETRIEVAL / RAG

Use the `search_tax_documents` tool when the user asks about information
that may be contained in the official tax documents.

Examples include:
- "Who can file ITR-1?"
- "What documents are required for ITR-2?"
- "How do I file ITR-1 online?"
- "What are the validation rules?"
- "Is this income allowed under ITR-1?"
- "What does the ITR-2 manual say about this?"
- "Explain this section of the tax document."

Pass the user's question, or the relevant reformulated question, to
`search_tax_documents`.

The tool performs the embedding generation and vector search internally.

After receiving the retrieved results:
- use them as the factual basis for the answer
- preserve the meaning of the official documentation
- explain the information in simple language
- mention the document name and page number when useful
- do not fabricate information that is not supported by the retrieved
  documents

Do not expose internal implementation details such as embeddings,
BigQuery, SQL, VECTOR_SEARCH, or tool execution unless the user asks
about the technical architecture.

--------------------------------------------------

4. PROCESS PATHFINDING

When the user selects an Income Tax process and provides information
about their available documents, use the `roadmap` tool to determine
the clearest and easiest completion path.

Do not invent process steps when the roadmap tool can provide them.

--------------------------------------------------

5. SUBPROCESS GUIDANCE

If the user is missing documents required for a process, use the
`subprocess_roadmap` tool to provide clear and actionable instructions
for obtaining the missing documents.

Explain what the document is and why it may be needed.

--------------------------------------------------

6. VIDEO TUTORIALS

When the user would benefit from a visual walkthrough, use the
`video_fetcher` tool to find relevant YouTube tutorials.

Prefer tutorials that are relevant to the specific Income Tax
Department process being discussed.

Do not present a video as an official Income Tax Department source
unless it actually is an official source.

--------------------------------------------------

7. TOOL SELECTION

Use the appropriate tool based on the user's request.

- `search_tax_documents` → retrieve information from official tax
  documents
- `get_processes` → identify or retrieve available Income Tax processes
- `roadmap` → determine the completion path for a selected process
- `subprocess_roadmap` → help obtain missing documents or complete
  required subprocesses
- `video_fetcher` → retrieve relevant video tutorials

Use more than one tool when necessary.

Do not call tools unnecessarily for casual conversation or questions
that do not require their information.

--------------------------------------------------

8. ROOT AGENT RESPONSIBILITY

You are the root/orchestrator agent.

Your responsibility is to understand the user's request and decide
which specialized capability or tool is appropriate.

When the user asks a question requiring official tax-document
information, retrieve that information using `search_tax_documents`
before relying on general knowledge.

When the user wants to complete a specific Income Tax process, use the
appropriate process and roadmap tools.

After obtaining information from tools, synthesize the results into
one clear response for the user.

Do not expose internal agent routing or tool-selection decisions to
the user.

--------------------------------------------------

9. COMMUNICATION STYLE

Be clear, concise, friendly, and practical.

Avoid unnecessary tax jargon.

When using a tax term, explain it briefly in simple language.

Do not overwhelm the user with large amounts of information.

Give the user the next useful step whenever possible.

--------------------------------------------------

10. UNCERTAINTY

Tax rules and government procedures can change.

If information is uncertain, incomplete, conflicting, or potentially
outdated:

- clearly identify the uncertainty
- use the official document retrieval tool when appropriate
- do not fabricate an answer
- recommend verification against the latest official Income Tax
  Department guidance

--------------------------------------------------

PRIMARY GOAL

Understand the user's request
        ↓
Identify the appropriate capability
        ↓
Retrieve official information when necessary
        ↓
Use the appropriate tool
        ↓
Synthesize the information
        ↓
Give the user a clear and reliable next step

You are an informational assistant only and are not a substitute for
the official Income Tax Department portal, official documentation,
or professional tax advice.
"""
)

print("Agent started")

tax_assistant_agent = Agent(
    name="IncomeTaxPortalAgent",
    model="gemini-2.5-flash",
    description="Authoritative, Read-Only AI Agent for Income Tax Portal Services & Roadmap Guidance.",
    instruction=agent_system_instruction,
    tools=[get_processes, roadmap, subprocess_roadmap, video_fetcher, search_tax_documents]
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
# REGIME CALCULATOR  (FY 2024-25 / AY 2025-26)
# =====================================================================

def regime_calculator(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes the user profile dict returned by extract_user_profile_from_session
    and calculates income tax liability under both the Old and New tax regimes
    for FY 2024-25 (AY 2025-26).

    Returns a structured dict with:
      - old_regime:   breakdown + total tax
      - new_regime:   breakdown + total tax
      - recommendation: which regime to pick and a plain-English explanation
      - savings:      how much the recommended regime saves
    """

    # ── 1. Unpack profile ────────────────────────────────────────────
    emp   = user_profile.get("employment", {})
    add   = user_profile.get("additional_income", {})
    ded   = user_profile.get("deductions", {})
    fil   = user_profile.get("filing", {})

    gross_salary        = float(emp.get("annual_salary")   or 0)
    other_income        = float(emp.get("other_income")    or 0)
    capital_gains_amt   = float(add.get("capital_gains_amount")  or 0)
    rental_income_amt   = float(add.get("rental_income_amount")  or 0)

    home_loan_interest  = float(ded.get("home_loan_interest") or 0)
    section_80c         = min(float(ded.get("section_80c")     or 0), 150_000)   # capped at ₹1.5L
    health_insurance    = min(float(ded.get("health_insurance") or 0), 50_000)   # 80D capped at ₹50k (self+parents)
    nps                 = min(float(ded.get("nps")             or 0), 50_000)    # 80CCD(1B) capped at ₹50k
    hra_amount          = float(ded.get("hra_amount")          or 0)

    employment_type     = (emp.get("employment_type") or "salaried").lower()

    # ── 2. Gross Total Income ────────────────────────────────────────
    gross_total = gross_salary + other_income + rental_income_amt + capital_gains_amt

    # ── 3. OLD REGIME ────────────────────────────────────────────────
    #   Standard deduction  : ₹50,000 (salaried/pensioner)
    #   HRA exemption       : actual HRA received (simplified; exact calc needs rent paid & city)
    #   Home loan interest  : Sec 24(b) up to ₹2,00,000
    #   80C                 : up to ₹1,50,000
    #   80D                 : up to ₹50,000
    #   80CCD(1B) NPS       : up to ₹50,000

    old_standard_deduction = 50_000 if employment_type in ("salaried", "retired") else 0
    old_hra_exempt         = min(hra_amount, gross_salary * 0.4)       # simplified 40% rule
    old_home_loan_deduction= min(home_loan_interest, 200_000)
    old_80c                = section_80c
    old_80d                = health_insurance
    old_80ccd              = nps

    old_total_deductions = (
        old_standard_deduction
        + old_hra_exempt
        + old_home_loan_deduction
        + old_80c
        + old_80d
        + old_80ccd
    )

    old_taxable_income = max(gross_total - old_total_deductions, 0)
    old_tax_before_cess, old_slab_breakdown = _compute_old_tax(old_taxable_income)

    # Rebate u/s 87A: full rebate if taxable income ≤ ₹5L (old regime)
    old_rebate_87a = old_tax_before_cess if old_taxable_income <= 500_000 else 0
    old_tax_after_rebate = max(old_tax_before_cess - old_rebate_87a, 0)

    old_cess  = round(old_tax_after_rebate * 0.04, 2)          # 4% health & education cess
    old_total_tax = round(old_tax_after_rebate + old_cess, 2)

    # ── 4. NEW REGIME ────────────────────────────────────────────────
    #   Standard deduction  : ₹75,000 (salaried/pensioner) — enhanced from FY 2024-25 Budget
    #   Most deductions NOT available (80C, 80D, HRA, home loan interest etc.)
    #   80CCD(1B) NPS employer contribution still allowed but we keep it simple

    new_standard_deduction = 75_000 if employment_type in ("salaried", "retired") else 0
    new_total_deductions   = new_standard_deduction     # only std deduction allowed

    new_taxable_income = max(gross_total - new_total_deductions, 0)
    new_tax_before_cess, new_slab_breakdown = _compute_new_tax(new_taxable_income)

    # Rebate u/s 87A: full rebate if taxable income ≤ ₹7L (new regime from FY 2023-24)
    new_rebate_87a = new_tax_before_cess if new_taxable_income <= 700_000 else 0
    new_tax_after_rebate = max(new_tax_before_cess - new_rebate_87a, 0)

    new_cess      = round(new_tax_after_rebate * 0.04, 2)
    new_total_tax = round(new_tax_after_rebate + new_cess, 2)

    # ── 5. Recommendation ────────────────────────────────────────────
    savings    = abs(old_total_tax - new_total_tax)
    better     = "old" if old_total_tax < new_total_tax else "new"
    tie        = old_total_tax == new_total_tax

    if tie:
        recommendation = "either"
        explanation = (
            "Both regimes result in the same tax liability of "
            f"₹{old_total_tax:,.0f}. You may choose either — "
            "the New Regime is simpler since it requires no investment proofs."
        )
    elif better == "old":
        explanation = (
            f"The Old Regime saves you ₹{savings:,.0f} compared to the New Regime. "
            f"This is because your total deductions (₹{old_total_deductions:,.0f}) — "
            f"including 80C (₹{old_80c:,.0f}), health insurance 80D (₹{old_80d:,.0f}), "
            f"home loan interest Sec 24(b) (₹{old_home_loan_deduction:,.0f}), "
            f"HRA exemption (₹{old_hra_exempt:,.0f}), and NPS 80CCD(1B) (₹{old_80ccd:,.0f}) — "
            f"reduce your taxable income significantly to ₹{old_taxable_income:,.0f}, "
            f"which offsets the lower slab rates of the New Regime."
        )
    else:
        explanation = (
            f"The New Regime saves you ₹{savings:,.0f} compared to the Old Regime. "
            f"Even though your deductions under the Old Regime total ₹{old_total_deductions:,.0f}, "
            f"the lower slab rates in the New Regime (especially the higher ₹75,000 standard deduction "
            f"and the ₹7L rebate threshold) result in a lower tax of ₹{new_total_tax:,.0f} "
            f"vs ₹{old_total_tax:,.0f} under the Old Regime. "
            "The New Regime is also simpler — no investment proofs needed."
        )

    return {
        "gross_total_income": round(gross_total, 2),
        "old_regime": {
            "deductions": {
                "standard_deduction": old_standard_deduction,
                "hra_exemption":      round(old_hra_exempt, 2),
                "home_loan_sec24b":   old_home_loan_deduction,
                "section_80c":        old_80c,
                "section_80d":        old_80d,
                "nps_80ccd1b":        old_80ccd,
                "total":              round(old_total_deductions, 2),
            },
            "taxable_income":   round(old_taxable_income, 2),
            "slab_breakdown":   old_slab_breakdown,
            "tax_before_cess":  round(old_tax_before_cess, 2),
            "rebate_87a":       round(old_rebate_87a, 2),
            "cess_4pct":        old_cess,
            "total_tax":        old_total_tax,
        },
        "new_regime": {
            "deductions": {
                "standard_deduction": new_standard_deduction,
                "total":              new_total_deductions,
            },
            "taxable_income":   round(new_taxable_income, 2),
            "slab_breakdown":   new_slab_breakdown,
            "tax_before_cess":  round(new_tax_before_cess, 2),
            "rebate_87a":       round(new_rebate_87a, 2),
            "cess_4pct":        new_cess,
            "total_tax":        new_total_tax,
        },
        "recommendation": {
            "choose":      "tie" if tie else better,
            "old_tax":     old_total_tax,
            "new_tax":     new_total_tax,
            "savings":     round(savings, 2),
            "explanation": explanation,
        },
    }


# ── Slab helpers ─────────────────────────────────────────────────────

def _apply_slabs(taxable_income: float, slabs: List[Dict]) -> tuple[float, List[Dict]]:
    """
    Generic slab engine.
    slabs: list of {"up_to": int|None, "rate": float, "label": str}
      up_to=None means the top (unbounded) slab.
    Returns (total_tax, breakdown_list).
    """
    tax = 0.0
    breakdown = []
    prev = 0

    for slab in slabs:
        limit = slab["up_to"]
        rate  = slab["rate"]
        label = slab["label"]

        if taxable_income <= prev:
            break

        slab_income = (taxable_income - prev) if limit is None else min(taxable_income - prev, limit - prev)
        slab_tax    = slab_income * rate
        tax        += slab_tax

        if slab_income > 0:
            breakdown.append({
                "slab":        label,
                "slab_income": round(slab_income, 2),
                "rate":        f"{int(rate * 100)}%",
                "tax":         round(slab_tax, 2),
            })

        if limit is None:
            break
        prev = limit

    return tax, breakdown


def _compute_old_tax(taxable_income: float) -> tuple[float, List[Dict]]:
    """Old regime slabs for individual below 60 (FY 2024-25)."""
    slabs = [
        {"up_to":  250_000, "rate": 0.00, "label": "Up to ₹2.5L"},
        {"up_to":  500_000, "rate": 0.05, "label": "₹2.5L – ₹5L   @  5%"},
        {"up_to": 1_000_000,"rate": 0.20, "label": "₹5L  – ₹10L   @ 20%"},
        {"up_to": None,      "rate": 0.30, "label": "Above ₹10L    @ 30%"},
    ]
    return _apply_slabs(taxable_income, slabs)


def _compute_new_tax(taxable_income: float) -> tuple[float, List[Dict]]:
    """New regime slabs (FY 2024-25, post-Budget 2024 revision)."""
    slabs = [
        {"up_to":  300_000, "rate": 0.00, "label": "Up to ₹3L"},
        {"up_to":  700_000, "rate": 0.05, "label": "₹3L – ₹7L     @  5%"},
        {"up_to": 1_000_000,"rate": 0.10, "label": "₹7L – ₹10L    @ 10%"},
        {"up_to": 1_200_000,"rate": 0.15, "label": "₹10L – ₹12L   @ 15%"},
        {"up_to": 1_500_000,"rate": 0.20, "label": "₹12L – ₹15L   @ 20%"},
        {"up_to": None,      "rate": 0.30, "label": "Above ₹15L    @ 30%"},
    ]
    return _apply_slabs(taxable_income, slabs)


if __name__ == "__main__":
    print("=" * 70)
    print(f"🤖 Agent Initialized: {tax_assistant_agent.name}")
    print(f"📦 Framework: Google Agent Development Kit (google-adk v2.7.0)")
    print(f"🧠 Model: {tax_assistant_agent.model}")
    print(f"🛠️ Configured Tools: {[t.__name__ for t in tax_assistant_agent.tools]}")
    print("=" * 70)

    # 1. Test get_processes
    print("\n--- 1. Testing get_processes() ---")
    all_p = get_processes()
    for p in all_p:
        print(f" • [{p['process_id']}] {p['name']} -> {p['official_url']}")

    # 2. Test roadmap using UI data read from main.py
    selected_svc, active_documents = get_main_selection()
    print(f"\n--- 2. Testing roadmap('{selected_svc}', {active_documents}) [Data read from main.py] ---")
    rm = roadmap(selected_svc, active_documents)
    print(f"Process: {rm['process_name']}")
    print(f"Missing Docs: {rm['missing_documents']}")
    print("Completion Path:")
    for step in rm['completion_path']:
        print(f"   {step}")

    # 3. Test subprocess_roadmap
    print("\n--- 3. Testing subprocess_roadmap(missing_documents) ---")
    sub_rm = subprocess_roadmap(rm['missing_documents'])
    for guide in sub_rm["acquisition_roadmap"]:
        print(f" • Document: {guide['document']}")
        print(f"   Source: {guide['source']}")
        print(f"   Steps: {guide['steps']}")

    # 4. Test video_fetcher dynamically based on main.py selection & missing docs
    print(f"\n--- 4. Testing video_fetcher('{selected_svc}', missing_docs={rm['missing_documents']}) ---")
    vids = video_fetcher(query=selected_svc, missing_documents=rm['missing_documents'])
    for v in vids:
        print(f" 🎥 {v['title']} ({v['channel']}) -> {v['url']}")
