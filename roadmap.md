# STEP-BY-STEP CAPSTONE ROADMAP

PHASE 0 - PROJECT SETUP

Goal:
Build the repository like a real product rather than a school assignment.

Repository Structure:

employee-operations-agent/

* README.md
* CLAUDE.md
* requirements.txt
* .env
* docs/
* policies/
* prompts/
* src/
* tests/
* rag/
* tools/
* agents/
* workflows/
* mcp_server/
* service_now/
* data/
* evaluation/
* ui/

Tech Stack:

* Python
* LangGraph
* Anthropic Models
* ChromaDB
* Sentence Transformers
* ServiceNow APIs
* MCP
* LangChain
* FastAPI (optional)
* Streamlit or provided UI
* GitHub

---

PHASE 1 - COMPLETE PTO AGENT REQUIREMENTS

This is your MVP.

Capabilities:

1. Policy Questions
2. Check Balance
3. Submit PTO Request
4. List Requests

Required Features:

* RAG
* Tool Calling
* LangGraph
* Clarification Questions
* Confirmation before submission
* Validation checks
* Error handling
* Human in the loop
* Prompt engineering
* grounding
* context management

---

PHASE 2 - MAKE THE PTO AGENT IMPRESSIVE

Add:

* pending request tracking
* reserve PTO days
* manager approvals
* calendar integration
* notifications
* conflict checking

Examples:

"You already have PTO pending from July 10-12."

"Your manager is out on those dates."

"You only have 4 PTO days remaining."

---

PHASE 3 - REAL DATABASE

DO NOT STAY WITH JSON LONG TERM.

Start:

employees.json
balances.json
requests.json

Then move to:

SQLite

Eventually:

PostgreSQL

Database Tables:

Employees

* id
* role
* manager_id
* location
* country

PTO Requests

* employee_id
* leave_type
* status
* start_date
* end_date

Balances

* PTO
* Sick Leave
* Parental Leave

Approvals

* manager
* status
* comments

Expenses

Equipment Requests

Benefits

Travel Requests

This makes the project much more realistic.

---

PHASE 4 - SERVICENOW INTEGRATION

Replace:

JSON --> Database --> ServiceNow APIs

Architecture:

Agent

↓

Tool Calling

↓

ServiceNow API Tool

↓

ServiceNow Instance

Examples:

check_balance_tool()

submit_pto_request_tool()

list_requests_tool()

manager_approval_tool()

The LLM should NEVER directly manipulate data.

The LLM decides:

"What tool should I use?"

The tool performs:

* calculations
* API calls
* validation
* database operations

---

PHASE 5 - MANAGER ROLE

Add:

Manager persona.

Capabilities:

* approve PTO
* reject PTO
* view team calendar
* team availability
* upcoming absences
* team leave statistics

Questions:

"Who is out tomorrow?"

"Can everyone attend Friday's meeting?"

"Approve Ishani's PTO request."

---

PHASE 6 - ENTERPRISE EMPLOYEE OPERATIONS AGENT

The PTO agent becomes one capability.

Modules:

1. PTO

2. Expense Reimbursement

3. Equipment Requests

4. HR Policies

5. Benefits

6. Payroll FAQs

7. Travel Approvals

8. Employee Onboarding

Each capability is implemented as tools and workflows.

---

PHASE 7 - MULTI AGENT ARCHITECTURE

DO NOT START HERE.

Start with:

single orchestrator

Then evolve into:

Supervisor Agent

↓

Employee Operations Router Agent

↓

PTO Agent

↓

HR Agent

↓

Payroll Agent

↓

Travel Agent

↓

Benefits Agent

↓

Expense Agent

Each specialized agent can have:

* prompts
* tools
* RAG
* workflows

This architecture scales naturally.

---

PHASE 8 - MODEL SELECTION

Use Claude models intelligently.

Haiku:

* intent classification
* routing
* extraction
* simple questions

Sonnet:

* tool selection
* reasoning
* RAG responses
* workflow decisions

Opus:

* complex reasoning
* manager decisions
* multi-step planning
* difficult policy questions

This demonstrates cost optimization.

---

PHASE 9 - PROMPT ENGINEERING

Use:

RCTFC

Role
Context
Task
Format
Constraints

Prompting Techniques:

* Zero Shot
* Few Shot
* Chain of Thought
* Structured Outputs

Separate:

System Prompts

User Prompts

Tool Descriptions

Examples:

policy_prompt.md

router_prompt.md

approval_prompt.md

clarification_prompt.md

manager_prompt.md

---

PHASE 10 - RAG ARCHITECTURE

Policy Documents

↓

Chunking

↓

Embeddings

↓

ChromaDB

↓

Semantic Search

↓

Retrieved Context

↓

Grounded Generation

Use:

* metadata filtering
* country filtering
* semantic similarity search

Metadata:

* country
* leave type
* document source

Chunking Strategy:

DO NOT USE FIXED CHARACTER CHUNKS.

Use:

* section based chunking
* country based chunking
* overlap where appropriate

Include experiments showing:

BAD chunking

vs

GOOD chunking

This is literally one of the bootcamp learning objectives.

---

PHASE 11 - TOOLS

Tools should handle:

PTO:

* check balance
* submit request
* list requests

Utilities:

* days_between
* calendar checker
* PTO calculator

RAG:

* retrieve_policy()

ServiceNow:

* API tools

Database:

* query_employee()

Manager:

* approve request()

External:

* Google Calendar APIs
* Outlook APIs

The AI should NEVER do math itself.

---

PHASE 12 - MCP

Expose:

* PTO tools
* HR tools
* manager tools

via MCP.

This makes your project interoperable.

Imagine:

Claude Desktop

↓

discovers

↓

check_pto_balance

submit_request

approve_request

This is very impressive in interviews.

---

PHASE 13 - MEMORY MANAGEMENT

Short Term Memory:

conversation state.

Context Management:

* pruning
* sliding window
* summarization
* conversation compression

Store:

employee context

NOT:

entire conversation history

Keep:

* first messages
* recent messages
* workflow state

---

PHASE 14 - SAFETY

Prompt Injection Protection:

Never trust:

* policy documents
* user inputs
* retrieved documents

Policy text is:

DATA

NOT INSTRUCTIONS.

Other protections:

* identity validation
* authorization
* tool restrictions
* no cross employee access
* role validation
* API validation

Example:

User:

"Submit PTO for John."

Response:

"I can only perform actions for the currently authenticated employee."

---

PHASE 15 - ERROR HANDLING

Never Fail Silently.

Handle:

* invalid dates
* insufficient balance
* ServiceNow API failures
* missing information
* tool failures
* manager rejection
* retrieval failures

Examples:

"I couldn't retrieve your balance."

NOT:

"Your balance is zero."

---

PHASE 16 - EVALUATIONS

DO THIS LAST.

Evaluate:

* retrieval quality
* tool accuracy
* policy grounding
* workflow success
* safety
* clarification handling
* hallucination rate

---

FINAL VERSION OF THE PROJECT

Employee Operations Agent

Capabilities:

Employee:

* PTO
* HR policies
* payroll
* travel
* benefits
* expenses
* equipment requests
* onboarding

Managers:

* approvals
* team availability
* analytics

Architecture:

* Multi Agent
* LangGraph
* Tool Calling
* RAG
* MCP
* ServiceNow APIs
* Database
* Multiple Claude Models
* Prompt Engineering
* Human in the Loop
* Memory Management
* Security
* Evaluations

This should feel like a small version of an actual ServiceNow product rather than a class project.
