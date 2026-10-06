# ERP AI Analytics - Combined Documentation

This repository is the **erp-bot** implementation of the HNS "AI-Based Sales
Analytics & Decision Intelligence Platform" - a working, deployed
conversational analytics system for Best Marine Private Limited. This single
file carries a project description (architecture and implementation) followed
by the repository's three consolidated documents: the **HNS platform design
specification**, the **erp-bot implementation deep-dive**, and the **erp-bot
operational README**.

## Project Description - Architecture and Implementation

The repository implements the analytical core of the HNS platform. It loads
the ERP Excel exports under `data/` (Sales Orders, Sales Order Details, Sales
Invoice Details) into pandas DataFrames, exposes a registry of twelve
analytical tools over them, and lets an LLM drive those tools conversationally
to answer ad-hoc business questions. A fourth workbook (Sales Invoice
**header**) ships with the repo but is not ingested - defect **F-02**.

### Architecture

```mermaid
flowchart TB
    subgraph BROWSER["Browser - single-file vanilla JS frontend (index.html, 917 lines)"]
        UI["Chat UI<br/>auth modal<br/>markdown rendering"]
    end

    subgraph VERCEL["Vercel - @vercel/python WSGI (app.py)"]
        subgraph DJANGO["Django 5.2.7 + DRF - 4 API views (views.py)"]
            API["POST /api/ask/"]
        end
        subgraph AGENT["llm_api.agent - run_agent() tool loop, 6 iterations"]
            SYS["system prompt + 12 tool schemas<br/>(agent.py:20-182)"]
        end
        subgraph TOOLS["llm_api.analytics_tools - TOOL_REGISTRY, 12 tools"]
            LD["data_loader.load_data() - Excel to cached DataFrames"]
        end
    end

    subgraph LLM["LLM provider (OpenAI-compatible SDK)"]
        NIM["NVIDIA NIM<br/>nvidia/nemotron-3-ultra-550b-a55b (default)"]
        OAI["OpenAI - gpt-4o-mini (optional)"]
    end

    subgraph DATA["data/ - 3 workbooks ingested, ~211 KB"]
        SO["Sales Order"]
        SOD["Sales Order Details"]
        INV["Sales Invoice Details"]
    end

    UI -->|Bearer token selects provider| API
    API --> AGENT --> TOOLS
    AGENT --> NIM
    AGENT --> OAI
    TOOLS --> LD --> DATA
```

One conversational turn: the browser POSTs `{query, session_id}` to
`/api/ask/` with a Bearer token; the token selects the LLM provider
(`views.py:15-28`); `run_agent` sends the query plus the schemas of all 12
tools to the model; the model returns `tool_calls`; each call executes against
`TOOL_REGISTRY` on the cached DataFrames; the results come back as `tool`
messages and the loop repeats until the model answers or 6 iterations are
exhausted. A single Django WSGI process serves both the API and the
`index.html` frontend behind one Vercel catch-all rewrite.

### Implementation scope

What is implemented in this repository, as measured on the delivered data
(`[VERIFIED]` in Part II):

| Dimension | Implemented |
| --- | --- |
| Analytical tools | 12 tools in `analytics_tools.py` (10 working; 2 stubs - payment behaviour, sales returns) |
| Tool capability | Top-N, customer health, discontinuation, growth alerts, weekly trends, order-to-invoice, low-volume, revenue summary, deep-dives |
| LLM agent | `run_agent` - iterative tool-calling loop (`agent.py:231-305`), 6 iterations max, `max_tokens=16384` |
| Providers | NVIDIA NIM (default) + OpenAI, selected by auth token |
| API | 4 endpoints - `/api/ask/`, `/api/reload-data/`, `/api/session/<id>/`, `/api/health/` |
| Frontend | Single-page chat UI, vanilla JS, no build step |
| Dataset | 37 orders, 415 order-detail rows, 3,333 invoice rows (01-Apr to 06-May-2026) |
| Deployment | Vercel `@vercel/python`, auto-deploy from `main`, data bundled read-only |
| Measured latency | cold `load_data()` 1,631 ms (then cached); warm tool calls 0.85-161 ms |

### Requirements-to-implementation map

The HNS design (Part I) specifies five analytical modules; here is the status
of each in this codebase (evidenced in Part II):

| HNS required module (Part I) | Status in this repo (Part II) |
| --- | --- |
| 1 Customer Health & Discontinuation Intelligence | **PARTIAL** - health scores + discontinuation tools exist; no payment input, no confidence field |
| 2 Sales Bottleneck & Delay Analysis | **MISSING** - no delivery/PO data, no tool |
| 3 Regional Sales Intelligence | **MISSING** - no region attribute in any workbook |
| 4 Customer Potential Analysis | **MISSING** - no `potential` tool |
| 5 Trend & Opportunity Analysis | **PARTIAL** - trend + growth tools exist; defects F-03 / F-05 |
| Full order-to-cash coverage | **PARTIAL** - orders + invoices only; payment/returns are stubs |

Known defects (F-01..F-21) and security findings (S-1..S-8) are catalogued in
Part II, with the operational runbook in Part III.

### Document map

| Part | Content | Pre-merge source |
| --- | --- | --- |
| [Part I](#part-i-hns-platform-design-specification) | HNS - AI-Based Sales Analytics & Decision Intelligence Platform: project flow / architecture / design specification. Tags: `[OBSERVED]`, `[REQUIRED]`, `[PROPOSED]`, `[PSEUDOCODE]`, `[ASSUMPTION]`, `[BLOCKED]`. | `README.md` (1,657 lines) |
| [Part II](#part-ii-erp-ai-analytics-implementation-deep-dive) | ERP AI Analytics implementation audit: architecture, data layer, 12-tool catalogue, agent loop, API/auth, defect register F-01..F-21, security review S-1..S-8, trade-offs, measured timings, interview Q&A, verified figures. Tags: `[IMPLEMENTED]`, `[VERIFIED]`, `[OBSERVED]`, `[DESIGN]`, `[GAP]`, `[RISK]`, `[BLOCKED]`. | `PROJECT_FLOW.md` (2,109 lines) |
| [Part III](#part-iii-erp-ai-analytics-operational-readme) | Operational README: what it does, quick start (+ data-dir warning), env config, auth tokens, API endpoints, 12 tools, Vercel deploy, limitations, security notes. | `ERP_README.md` (298 lines) |

---

## Part I: HNS Platform Design Specification

*Reproduced verbatim from the original `README.md` (1,657 lines).*

---

# HNS — AI-Based Sales Analytics & Decision Intelligence Platform

Project Flow, Architecture and Engineering Design Document

**Project code:** HNS
**Document type:** Project flow / architecture / design specification
**Document version:** 1.0
**Source of requirements:** `AI_Sales_Analytics_POC_Requirement_Document.docx`
**Status:** Design specification built on top of a delivered data sample

---

## 0. How To Read This Document

This document describes the HNS platform: an AI-assisted sales analytics and
recommendation engine intended to analyse ERP transactional data and produce
interpreted, parameter-driven business recommendations.

Because the delivered repository contains a **requirement document and a data
sample only** — no application source code — every statement in this document is
explicitly tagged so that a reviewer can always separate evidence from design:

| Tag | Meaning |
| --- | --- |
| `[OBSERVED]` | Verified directly from the files in this repository. Numbers are reproducible from the workbooks described in §4. |
| `[REQUIRED]` | Stated by the client's requirement document. |
| `[PROPOSED]` | A design recommendation made by this document. Not implemented. |
| `[PSEUDOCODE]` | Illustrative algorithm, not production code. |
| `[ASSUMPTION]` | An inference that is plausible but not proven by the delivered data. Must be confirmed with the business. |
| `[BLOCKED]` | Cannot be computed or verified with the currently available data. |

Anything without a tag in a heading or table caption should be read as
`[PROPOSED]` design narrative.

---

## 1. Executive Summary

### 1.1 What the client wants `[REQUIRED]`

The requirement document asks for an "AI-Based Sales Analytics & Decision
Intelligence Platform" that:

- analyses the complete **Order-to-Cash** lifecycle — Sales Orders, Sales
  Invoices, Delivery information, Payment behaviour, Debit/Credit Notes, Sales
  Returns, customer trends and operational bottlenecks;
- implements five analytical modules — **Customer Health & Discontinuation
  Intelligence**, **Sales Bottleneck & Delay Analysis**, **Regional Sales
  Intelligence**, **Customer Potential Analysis**, and **Trend & Opportunity
  Analysis**;
- produces **explanations, justifications, supporting parameters, confidence
  levels and suggested actions**, not just numbers;
- is explicitly *not* a static dashboard;
- uses **parameter-driven scoring, fixed business logic, controlled prompts and
  structured analytical pipelines** to guarantee repeatability;
- starts with **NVIDIA free LLM APIs** and scales later toward OpenAI, Claude,
  Gemini, local LLMs and enterprise deployments;
- is validated on a **15-day to 1-month** historical sample.

### 1.2 What actually exists `[OBSERVED]`

The repository contains **five files and zero lines of code**:

```
HNS/
├── AI_Sales_Analytics_POC_Requirement_Document.docx
├── Sales Invoice - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16_Sales Invoice_Submitted + Draft_Date Wise Sales Invoice.xlsx
├── Sales Invoice Details - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16_Sales Invoice_Submitted + Draft__Date Wise Sales Invoice.xlsx
├── Sales Order - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16_Date Wise Sales Order.xlsx
└── Sales Order Details - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16__Submitted + Draft_Date Wise Sales Order.xlsx
```

There is no API specification, no database schema, no code, no configuration,
no infrastructure definition and no test suite.

### 1.3 The three findings that shape the entire design

**Finding 1 — The data is good, but it is a quarter of a month, not a quarter of a year.**
The usable sample is a single month of April 2026. Any "trend", "churn" or
"seasonality" module cannot be validated on this sample; it can only be
*architected*. This is the single most important constraint on the POC and it is
a scoping conversation, not an engineering problem.

**Finding 2 — The requirement asks for Order-to-Cash; the data is only Order-to-Invoice.**
Of the eight datasets named in §7 of the requirement (Customer Master, Sales
Orders, Sales Invoices, Payment Entries, Credit Notes, Debit Notes, Sales
Returns), **three exist** (Sales Orders, Sales Invoices — both header and child
tables) and **five are absent**. Critically, there is **no payment-entry
dataset**, so genuine payment *behaviour* — DSO, days-to-pay, payment slippage,
payment-frequency drift — is not measurable at all. `Outstanding Amount` is a
single snapshot balance, not a payment history.

**Finding 3 — Customer identity is fragmented, and fragmentation is the dominant analytical risk.**
The order export contains **12 distinct customer strings** and the invoice
export contains **33**, but only **7 appear in both**. Twenty-six customers
invoice without ever appearing on an order, and five appear on orders without
ever invoicing. On top of that, three invoice strings
(`Best Marine Exports`, `Best Marine Online`, `Best Marine Pvt Ltd Delhi`) are
almost certainly one customer group that together accounts for **50.91 %** of
invoiced value. Without entity resolution, a "customer risk" score is computed
against the wrong legal entity and the recommendation is wrong.

### 1.4 Verified baseline at a glance `[OBSERVED]`

| Metric | Sales Invoice | Sales Order |
| --- | --- | --- |
| Data rows (after footer removal) | 610 | 37 |
| Child / detail rows | 3,333 | 415 |
| Distinct documents | 610 | 37 (32 with lines) |
| Date range in data | 02-Apr-2026 → 30-Apr-2026 | 01-Apr-2026 → 29-Apr-2026 |
| Distinct dates | 15 | 12 |
| Net value (`Amt.Total`) | 10,408,405.39 | 4,549,969.80 |
| Gross value (`Grand Total`) | 10,829,459.06 | 5,106,918.32 |
| Taxes / charges | not in invoice export | 556,948.52 |
| Quantity (`Qty Total`) | 14,998 | 6,860 |
| Distinct customer strings | 33 | 12 |
| Distinct items | 182 | — |

### 1.5 Recommendation to the client

Proceed, but split the POC into two explicitly different tracks:

1. **Build track** — the deterministic, auditable analytics engine (ingestion,
   data quality, entity resolution, feature store, weighted rule engine,
   dashboards). This is fully achievable on the current data and is where all
   the durable business value sits.
2. **Validate track** — the LLM interpretation layer that consumes the rule
   engine's structured output and converts it into narrative, explanations and
   recommended actions. This is achievable, but its *quality* can only be
   judged once payment, delivery and returns data arrive.

Everything the requirement calls "AI" that is actually arithmetic should be
arithmetic. The LLM's job is interpretation and phrasing, not calculation.

---

## 2. Requirement Traceability Matrix `[REQUIRED] → [PROPOSED]`

| # | Requirement (source §) | Required capability | Data available now | Buildable now? |
| --- | --- | --- | --- | --- |
| R1 | §3 Order-to-Cash lifecycle | Full O2C modelling | Orders + invoices only | **Partially** — O2I only |
| R2 | §5 Module 1: Customer Health & Discontinuation Intelligence | Customer health score, churn early warning | Invoices + outstanding snapshot | **Partially** — health yes, churn not validatable |
| R3 | §5 Module 2: Sales Bottleneck & Delay Analysis | Cycle-time and delay root cause | Order→invoice link absent, no delivery | **Partially** — data-quality and order-side delays only |
| R4 | §5 Module 3: Regional Sales Intelligence | Region-wise performance | **No region field anywhere** | **No** — blocked on data |
| R5 | §5 Module 4: Customer Potential Analysis | Upsell / cross-sell potential | Item + quantity history for 1 month | **Partially** — descriptive only |
| R6 | §5 Module 5: Trend & Opportunity Analysis | Trends, seasonality, whitespace | 15–29 days only | **Architect only** |
| R7 | §6 AI reasoning | Explanation, parameters, confidence, actions | Derived from rule engine output | **Yes** |
| R8 | §10 Consistency & reliability | Parameter-driven, repeatable output | Deterministic rule engine | **Yes** |
| R9 | §9 Architecture | NVIDIA LLM first, swappable later | — | **Yes** — provider abstraction |
| R10 | §12 Output formats | Dashboards, summaries, risk cards, recommendation panels, exports, review summaries | — | **Yes** |
| R11 | §8 Validation | 15-day to 1-month sample | Exactly that | **Yes** — with stated limits |
| R12 | §13 Future scope | Forecasting, churn, demand, conversational AI, alerts | — | Deferred |

---

## 3. Proposed System Architecture

The requirement proposes four layers (§11). This document adopts those four
layers and decomposes each into concrete components.

### 3.1 Layer map `[PROPOSED]`

```mermaid
flowchart TD
    subgraph L1["Layer 1 — Data Ingestion"]
        A1["Excel / CSV Extract Reader"]
        A2["Schema Contract Validator"]
        A3["Data Quality Gate"]
        A4["Entity Resolution Service"]
        A5["Conformed Star Model"]
    end

    subgraph L2["Layer 2 — Business Rule Engine"]
        B1["Feature Store / KPI Library"]
        B2["Module 1: Customer Health"]
        B3["Module 2: Bottleneck and Delay"]
        B4["Module 3: Regional Sales"]
        B5["Module 4: Customer Potential"]
        B6["Module 5: Trend and Opportunity"]
        B7["Weighted Scoring and Ranking"]
        B8["Recommendation Policy Table"]
    end

    subgraph L3["Layer 3 — AI Interpretation Layer"]
        C1["Insight Composer"]
        C2["Prompt Registry and Templates"]
        C3["LLM Gateway - NVIDIA first, swappable"]
        C4["Output Schema Validator"]
        C5["Confidence and Evidence Binder"]
    end

    subgraph L4["Layer 4 — Visualization Layer"]
        D1["Interactive Dashboards"]
        D2["Customer Risk Cards"]
        D3["Recommendation Panel"]
        D4["Exportable Reports"]
        D5["Management Review Summary"]
    end

    A1 --> A2 --> A3 --> A4 --> A5
    A5 --> B1
    B1 --> B2 --> B7
    B1 --> B3 --> B7
    B1 --> B4 --> B7
    B1 --> B5 --> B7
    B1 --> B6 --> B7
    B7 --> B8
    B8 --> C1
    C1 --> C2 --> C3 --> C4 --> C5
    C5 --> D1
    C5 --> D2
    C5 --> D3
    C5 --> D4
    C5 --> D5
```

### 3.2 Layer 1 — Data Ingestion

Responsibility: turn four flat ERP exports into one trustworthy, versioned,
analytically-shaped dataset. This layer is where the real engineering effort
should go, because every downstream number depends on it.

| Component | Responsibility | Key design decision |
| --- | --- | --- |
| `extract_reader` | Reads `.xlsx` / `.csv` from a drop folder, parses the single `Query Report` sheet, records file name, size, mtime and SHA-256 | Content hash, not mtime, decides whether a re-run is needed |
| `schema_contract` | Declarative column contract per dataset: name, dtype, nullability, semantic role, unit | Contracts live in YAML so business users can extend them without a code change |
| `dq_gate` | Runs structural, referential and business-rule checks; emits a quality score and a blocking verdict | Failures are **quarantined**, not silently dropped |
| `entity_resolution` | Maps raw `Customer Name` strings onto a governed `customer_key`; maps free-text `Item Name` onto `item_key` | Deterministic rules first, fuzzy match only as a proposal a human confirms |
| `conformed_model` | Materialises the star schema in §5 | Versioned snapshots; every insight is reproducible against a snapshot id |

### 3.3 Layer 2 — Business Rule Engine

Responsibility: compute every number. No LLM touches arithmetic.

Design principles, in order of importance:

1. **Determinism** — same snapshot + same parameter set ⇒ byte-identical output.
2. **Auditability** — every published number links to the rows that produced it.
3. **Parameterisation** — weights, thresholds and bands live in configuration,
   not code, so the business can tune without a deployment.
4. **Modularity** — the five modules are independent and can be enabled
   individually as data arrives.

### 3.4 Layer 3 — AI Interpretation Layer

Responsibility: take the rule engine's structured output and produce the
narrative, the justification, the confidence statement and the recommended
action — the things the requirement calls "AI reasoning".

Design principles:

1. The LLM **never invents a number.** It may only restate numbers supplied in
   its input, and its output is schema-validated against the input.
2. Every generation is **controlled by a versioned prompt template** stored in a
   prompt registry, with a pinned model id and temperature.
3. Every output carries an **evidence list** of `metric_id`s consumed from the
   rule engine.
4. A **deterministic narrative fallback** exists: if the LLM call fails or
   fails validation, a templated sentence generator produces the insight from
   the same metric set. The dashboard never goes blank because a third-party
   API was down.

### 3.5 Layer 4 — Visualization Layer

| Surface | Audience | Content |
| --- | --- | --- |
| Executive dashboard | Management | Revenue, realisation, concentration, top risks, top opportunities |
| Customer risk card | Sales / accounts | Health score, component scores, drivers, confidence, recommended action |
| Recommendation panel | Sales / ops | Ranked actions with expected value and effort |
| Module dashboards | Analysts | One per analytical module, with drill-down to source rows |
| Exportable report | Management review | Static snapshot with all parameters and snapshot id printed |

---

## 4. Delivered Dataset — Reverse-Engineered Specification

This section is entirely `[OBSERVED]`. It is the ground truth on which the
proposed architecture must operate.

### 4.1 Extraction conventions `[OBSERVED]`

- Every workbook contains a **single worksheet named `Query Report`**.
- Each sheet has **one header row**, one row per transaction header or line,
  and a **final `Grand Total` footer row** whose first cell is the literal
  string `Grand Total`.
- Filtering rule that is applied before any computation:

  ```python
  DATA_ROW = df.iloc[:, 0].astype(str).str.match(r"^\d{2}-[A-Za-z]{3}-\d{2}$")
  df = df[df[DATA_ROW]].reset_index(drop=True)
  ```

  This regex matches the real posting dates (`02-Apr-26`) and rejects the
  `Grand Total` footer. **This single step is critical** — an unfiltered frame
  silently inflates every total by one row and is the most common way this kind
  of ERP extract gets mis-analysed.

### 4.2 Sales Invoice header `[OBSERVED]`

**File:** `Sales Invoice - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16_Sales Invoice_Submitted + Draft_Date Wise Sales Invoice.xlsx`

| # | Column | Observed dtype | Semantic role |
| --- | --- | --- | --- |
| 0 | `Date` | text `dd-MMM-yy` | Invoice date |
| 1 | `Customer Name` | text | Party ledger name |
| 2 | `Amt.Total` | number | Invoice value **excluding** tax/charges |
| 3 | `Qty Total` | number | Header quantity (mixed UoM, see §4.8) |
| 4 | `Grand Total` | number | Invoice value **including** tax/charges |
| 5 | `Outstanding Amount` | number | Residual balance at export time |
| 6 | `Due Date` | text `dd-MMM-yy` | Payment due date |
| 7 | `Doc.No.` | text | Invoice number — **primary key** |

**Row accounting:** 611 raw rows − 1 footer = **610 data rows**, all with a
distinct `Doc.No.`.

### 4.3 Sales Invoice detail `[OBSERVED]`

**File:** `Sales Invoice Details - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16_Sales Invoice_Submitted + Draft__Date Wise Sales Invoice.xlsx`

| # | Column | Observed dtype | Semantic role |
| --- | --- | --- | --- |
| 0 | `Posting Date` | text `dd-MMM-yy` | Line posting date |
| 1 | `Customer Name` | text | Party ledger name |
| 2 | `Item Name` | text | Free-text item description |
| 3 | `Qty` | number | Line quantity |
| 4 | `Uom` | text | Unit of measure — `Nos` or `Pair` |
| 5 | `Rate` | number | Unit rate |
| 6 | `Amount` | number | **Extended, tax-exclusive** line value |
| 7 | `Item Sl No.` | number | Line sequence |
| 8 | `Doc.No.` | text | Foreign key → invoice header |

**Row accounting:** 3,334 raw − 1 footer = **3,333 line rows** across **610**
distinct documents.

### 4.4 Sales Order header `[OBSERVED]`

**File:** `Sales Order - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16_Date Wise Sales Order.xlsx`

| # | Column | Observed dtype | Semantic role |
| --- | --- | --- | --- |
| 0 | `Date` | text `dd-MMM-yy` | Order date |
| 1 | `Customer Name` | text | Party ledger name |
| 2 | `Qty Total` | number | Header quantity |
| 3 | `Amt.Total` | number | Order value excluding tax |
| 4 | `Grand Total` | number | Order value including tax |
| 5 | `Doc.No.` | text | Order number — **primary key** |
| 6 | `Total Taxes/Charges` | number | Tax/charge total |
| 7 | `Discount Amt` | number | Discount, zero on all 37 rows |

**Row accounting:** 38 raw − 1 footer = **37 data rows**, all with a distinct
`Doc.No.`.

### 4.5 Sales Order detail `[OBSERVED]`

**File:** `Sales Order Details - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16__Submitted + Draft_Date Wise Sales Order.xlsx`

| # | Column | Observed dtype | Semantic role |
| --- | --- | --- | --- |
| 0 | `Posting Date` | text `dd-MMM-yy` | Line posting date |
| 1 | `Customer Name` | text | Party ledger name |
| 2 | `Item Name` | text | Free-text item description |
| 3 | `Qty` | number | Line quantity |
| 4 | `Uom` | text | Unit of measure |
| 5 | `Rate` | number | Unit rate |
| 6 | `Amount` | number | Extended, tax-exclusive line value |
| 7 | `Sl No.Item` | number | Line sequence |
| 8 | `Doc.No.` | text | Foreign key → order header |

**Row accounting:** 416 raw − 1 footer = **415 line rows** across **32**
distinct documents.

### 4.6 Reference-integrity report `[OBSERVED]`

| Relationship | Result | Verdict |
| --- | --- | --- |
| Invoice header `Doc.No.` → invoice detail | 610 / 610 matched | **Clean** |
| Invoice detail `Amount` summed vs header `Amt.Total` | 610 / 610 exact to 2 dp | **Clean** |
| Invoice detail `Qty` summed vs header `Qty Total` | 610 / 610 exact | **Clean** |
| Order header `Doc.No.` → order detail | 32 / 37 matched | **5 orphans** |
| Order detail `Amount` summed vs header `Amt.Total` (matched only) | 32 / 32 exact | **Clean** |
| Order detail `Qty` summed vs header `Qty Total` (matched only) | 32 / 32 exact | **Clean** |
| Order detail documents with no header | 0 | **Clean** |

So the invoice side is internally perfect. **The order side is not.**

#### 4.6.1 The five orphan orders — root cause `[OBSERVED]`

This is worth writing out in full because it is the concrete example that
justifies the data-quality gate in Layer 1.

| Order `Doc.No.` | Date | Customer | Qty | Net | Gross | Diagnosis |
| --- | --- | --- | --- | --- | --- | --- |
| `SO-2526-MH00265-1` | 01-Apr-26 | Dynacom Tankers Management Pvt Ltd | 6 | 6,120.00 | 6,426.00 | No detail rows; **no twin document exists** |
| `SO-2526-MH00265-2` | 01-Apr-26 | Dynacom Tankers Management Pvt Ltd | 6 | 6,120.00 | 6,426.00 | Byte-identical twin of the row above; no detail rows |
| `SO-2627-AD00007` | 09-Apr-26 | Executive Ship Management Pte Ltd | 406 | 193,106.00 | 202,761.30 | `SO-2627-AD00007-1` **exists with identical qty, net and gross**; its 17 detail lines sum to exactly 193,106.00 / 406 |
| `SO-2627-AD00013` | 14-Apr-26 | Bureau Veritas India Pvt Ltd | 33 | 75,570.00 | 79,348.50 | `SO-2627-AD00013-1` **exists with identical qty, net and gross**; its 4 detail lines sum to exactly 75,570.00 / 33 |
| `SO-2627-MH00005` | 07-Apr-26 | Hydra Safety Trading Llc | 267 | 4,088.12 | 4,088.12 | `SO-2627-MH00005-1` exists but with **different** values (16 lines, 3,790.12, qty 247) — a genuine mismatch, not a suffix artefact |

Two distinct failure modes are present:

- **Mode A — suffixing.** For `SO-2627-AD00007` and `SO-2627-AD00013` the line
  items were posted under a `-1` suffixed document number. The header and the
  detail describe the *same* order. A naive join reports "missing lines"; the
  business reality is "lines filed under the wrong number". Treating these as
  zero-line orders would understate order fulfilment analysis for two orders
  worth 268,676.00 net.
- **Mode B — genuine gap.** `SO-2526-MH00265-1` and `SO-2526-MH00265-2` are an
  apparently duplicated pair with no lines and no suffixed twin. Either the
  order was never released to billing, or the line extract is incomplete.
  These must go to the business for confirmation — the engine must not guess.
- **Mode C — value conflict.** `SO-2627-MH00005` versus `SO-2627-MH00005-1`
  differ in both quantity (267 vs 247) and value (4,088.12 vs 3,790.12), a
  297.00 difference. Auto-linking them would be wrong; a human decides.

### 4.7 Customer fragmentation `[OBSERVED]`

| Set | Count |
| --- | --- |
| Distinct customer strings in the order export | 12 |
| Distinct customer strings in the invoice export | 33 |
| Present in **both** exports | 7 |
| Order-only (ordered, never invoiced in sample) | 5 |
| Invoice-only (invoiced, never ordered in sample) | 26 |

Order-only: `Akrotiri Tankers Ltd`, `Bureau Veritas India Pvt Ltd`,
`DELOS NAVIGATION LTD.`, `Osm Fleet Management India Private Limited`,
`Sarvam Safety Equipment Private Limited`.

Invoice-only includes 24 real counterparties plus **`Cash Sale`**, which is not
a customer at all — it is a counterparty placeholder for over-the-counter
transactions (75 invoices, 133,391.69 gross). It must be bucketed as a channel,
not scored as a relationship.

**Consequence:** joining orders to invoices by `Customer Name` is unsafe, and
matching on 7 of 33 customers would discard the large majority of activity. The
engine must run on `customer_key` from the resolution service (§6), never on the
raw string.

#### 4.7.1 The Best Marine concentration `[OBSERVED]`

| Raw string | Invoices | Gross invoiced | Outstanding |
| --- | --- | --- | --- |
| `Best Marine Exports` | 20 | 5,011,852.93 | 5,011,855.00 |
| `Best Marine Pvt Ltd Delhi` | 7 | 477,050.19 | 0.00 |
| `Best Marine Online` | 12 | 24,735.45 | 24,736.00 |
| **Group total** | **39** | **5,513,638.57** | **5,036,591.00** |

- Group share of invoiced value: **50.91 %**.
- Single largest string share: **46.28 %**.
- Top 5 customers: **76.52 %**. Top 10 customers: **90.88 %**.

The group-level view is materially different from the string-level view:
`Best Marine Exports` looks catastrophically delinquent (≈100 % outstanding)
while `Best Marine Pvt Ltd Delhi` is fully settled. Whether these are genuinely
different entities with different credit terms or one group on one commercial
arrangement is exactly the question the client must answer — and it is the
single highest-value question in the dataset, because it governs 50 % of revenue.

### 4.8 Units of measure `[OBSERVED]`

Invoice detail UoM distribution:

| UoM | Line count | Share |
| --- | --- | --- |
| `Nos` | 2,664 | 79.9 % |
| `Pair` | 669 | 20.1 % |

`Qty Total = 14,998` at header level is therefore **not a physically meaningful
single quantity** — it adds individual items and pairs of items. Any
quantity-based KPI (units sold, average order size in units, demand signal) is
invalid unless it is split by UoM first. This is a small detail with large
downstream consequences.

### 4.9 Tax, gross-versus-net, and outstanding artefacts `[OBSERVED]`

- Invoice-level difference between `Grand Total` and detail `Amount` summed:
  **4.045 %** of net value — this is tax/charges, present on the header but not
  on lines. Comparisons must declare which basis they use. This document uses
  **net** for performance and **gross** for cash exposure.
- Outstanding sometimes **exceeds** the day's invoiced gross by a rounding
  amount. Example, 2026-04-03: invoiced gross 502,247.52, outstanding
  502,248.00. Example, `Best Marine Exports`: invoiced 5,011,852.93,
  outstanding 5,011,855.00. The conclusion is that `Outstanding Amount` is
  derived at a finer granularity than the rounded `Grand Total` shown on the
  header. Outstanding must therefore be treated as a **separate authoritative
  measure**, never recomputed as `Grand Total − allocated payments`, and never
  compared to gross with a zero-tolerance equality test.

### 4.10 Payment terms `[OBSERVED]`

Derived as `Due Date − Date`:

| Term | Invoices | Share |
| --- | --- | --- |
| 0 days | 507 | 83.1 % |
| 4 days | 2 | 0.3 % |
| 30 days | 101 | 16.6 % |

Two useful consequences:

1. Term 0 dominates. For those invoices, **any residual balance is already past
   its due date** — so the strict-overdue subset can be computed without
   payment history.
2. `[ASSUMPTION]` If the `Outstanding Amount` snapshot date is the export end
   date implied by the file name (16-May-2026), then term-0 invoices dated in
   April are **16 to 44 days past due**. This assumption must be confirmed
   before the number is shown to a customer of the business.

### 4.11 Coverage and concentration `[OBSERVED]`

| Metric | Value |
| --- | --- |
| Invoice date range (data) | 02-Apr-2026 → 30-Apr-2026 |
| Order date range (data) | 01-Apr-2026 → 29-Apr-2026 |
| Date range (file names) | 01-Apr-2026 → 16-May-2026 |
| Distinct invoice dates | 15 |
| Distinct order dates | 12 |
| Distinct invoice items | 182 |
| Top item share | 11.13 % (`Boilersuit-~-MOL-~-StatSafe-Orange…`) |
| Top 10 items share | 40.92 % |

**Note the discrepancy** `[OBSERVED]`: the file names advertise coverage through
16-May-2026 but no row in any of the four sheets is dated after 30-Apr-2026.
Either the extract range was widened at query time or the second half of May had
no transactions. The pipeline records both the declared range and the observed
range and raises a warning when they disagree — a silent gap is worse than a
loud one.

Item granularity is also free text with embedded delimiters (`-~-`, `-`, `;`),
which makes grouping unstable. See §6.2.

### 4.12 Order-side value summary `[OBSERVED]`

| Customer | Orders | Qty | Net | Gross | Tax % |
| --- | --- | --- | --- | --- | --- |
| Osm Fleet Management India Private Limited | 1 | 1,341 | 2,817,530.00 | 3,287,115.40 | 16.67 |
| Executive Ship Management Pte Ltd | 6 | 1,389 | 686,820.00 | 721,161.00 | 5.00 |
| Dynacom Tankers Management Pvt Ltd | 8 | 527 | 529,908.00 | 557,968.36 | 5.30 |
| Bureau Veritas India Pvt Ltd | 2 | 66 | 151,140.00 | 158,697.00 | 5.00 |
| Msc Shipmanagement Limited Cyprus | 1 | 178 | 114,610.00 | 120,340.50 | 5.00 |
| V.Ships India Pvt.Ltd. | 2 | 120 | 79,752.00 | 84,503.74 | 5.96 |
| Sarvam Safety Equipment Private Limited | 1 | 50 | 58,990.00 | 62,646.70 | 6.20 |
| Hydra Safety Trading Llc | 12 | 2,992 | 45,903.60 | 45,903.60 | 0.00 |
| Apeejay Shipping Limited | 1 | 54 | 43,200.00 | 45,360.00 | 5.00 |
| Shipskart Marine Private Limited | 1 | 19 | 20,579.85 | 21,608.85 | 5.00 |
| DELOS NAVIGATION LTD. | 1 | 86 | 1,046.20 | 1,098.52 | 5.00 |
| Akrotiri Tankers Ltd | 1 | 38 | 490.15 | 514.65 | 5.00 |

Observations that matter for design:

- **Extreme order-side concentration.** One order (`Osm Fleet`, 2,817,530.00)
  is **61.9 %** of total net order value.
- **Order value is far below invoice value** (4,549,969.80 vs 10,408,405.39
  net). `[ASSUMPTION]` The order export is almost certainly *filtered* — the
  file name contains `Date Wise Sales Order` without a status qualifier, but 37
  orders cannot plausibly be the month's only orders for a business invoicing
  10.4 M. Treat the order side as a **partial** extract and do not compute
  order-to-invoice conversion from it.
- **Tax rates are inconsistent**: 5.00 % predominates, but 16.67 %, 6.20 %,
  5.96 %, 5.30 % and 0.00 % all appear. `Hydra Safety Trading` at 0.00 % is
  either zero-rated or exempt. A tax module must not hard-code 5 %.
- **Discount is 0.00 on all 37 orders** in this sample — the column exists but
  carries no information. A discount analysis module has nothing to chew on yet.

---

## 5. Target Analytical Data Model `[PROPOSED]`

A conformed star schema, so that Layer 2 modules query stable, governed tables
rather than re-deriving logic per dashboard.

```mermaid
erDiagram
    CUSTOMER_DIM ||--o{ SALES_INVOICE_FACT : "billed to"
    CUSTOMER_DIM ||--o{ SALES_ORDER_FACT : "ordered by"
    ITEM_DIM ||--o{ INVOICE_LINE_FACT : "contains"
    ITEM_DIM ||--o{ ORDER_LINE_FACT : "contains"
    SALES_INVOICE_FACT ||--|{ INVOICE_LINE_FACT : "header lines"
    SALES_ORDER_FACT ||--o{ ORDER_LINE_FACT : "header lines"
    SALES_ORDER_FACT ||--o| INVOICE_FACT : "optional match"

    CUSTOMER_DIM {
        int customer_key PK
        string customer_code
        string customer_name_canonical
        string customer_legal_name
        string segment
        string country
        string region
        string channel
        decimal credit_limit
        int payment_terms_days
    }
    ITEM_DIM {
        int item_key PK
        string item_code
        string item_name_raw
        string item_name_normalised
        string item_family
        string uom_base
        bool is_active
    }
    SALES_ORDER_FACT {
        int order_key PK
        string order_doc_no UK
        int customer_key FK
        date order_date
        decimal net_value
        decimal tax_value
        decimal gross_value
        decimal qty_total
        int line_count
        string status_raw
    }
    SALES_ORDER_FACT ||--o{ ORDER_LINE_FACT : "header lines"
    SALES_INVOICE_FACT {
        int invoice_key PK
        string invoice_doc_no UK
        int customer_key FK
        int matched_order_key FK
        date invoice_date
        date due_date
        int terms_days
        decimal net_value
        decimal gross_value
        decimal outstanding_amount
        decimal qty_total
        string source_snapshot_id
    }
    INVOICE_LINE_FACT {
        bigint line_id PK
        int invoice_key FK
        int item_key FK
        string uom
        decimal qty
        decimal rate
        decimal amount
    }
    ORDER_LINE_FACT {
        bigint line_id PK
        int order_key FK
        int item_key FK
        string uom
        decimal qty
        decimal rate
        decimal amount
    }
    DQ_FINDING {
        int finding_id PK
        string dataset
        string rule_code
        string severity
        string entity_ref
        string message
        string resolution_state
    }
```

Key modelling decisions and their justification:

1. **`sales_invoice_fact.matched_order_key` is nullable and optional.** No
   reliable order→invoice foreign key exists in the delivered data (§2, R1).
   Modelling it as required would force a fabricated join.
2. **Tax on order headers but not invoice lines.** The invoice export has no tax
   column, only `Grand Total`. Storing `gross_value` and `net_value` on the
   invoice fact preserves both bases without fabricating a tax amount.
3. **`dq_finding` is a first-class table.** The five orphan orders in §4.6.1 are
   not edge cases to be fixed once; they are permanent, queryable facts that
   every published metric must be able to reference.
4. **No `region` column is populated** because no source column exists
   (§2, R4). It is present in the model and explicitly `NULL`, so that the
   Regional module can activate the day a region-bearing extract arrives.

---

## 6. Entity Resolution & Data Quality

### 6.1 Customer resolution `[PROPOSED]`

Deterministic, in strict priority order. No fuzzy matching in the serving path.

| Rule | Rule definition | Observed example |
| --- | --- | --- |
| R-1 | Exact match on normalised legal name | — |
| R-2 | Alias / DBA table lookup (governed, human-maintained) | `Best Marine Online` → `Best Marine Exports` group |
| R-3 | Parent–subsidiary map, only when the business confirms | `Best Marine Pvt Ltd Delhi` → group `Best Marine` |
| R-4 | Known non-customer bucket | `Cash Sale` → channel `counter` |
| R-5 | Unresolved → own `customer_key`, flagged `unverified` | — |

Normalisation steps, in order: trim, collapse internal whitespace, strip
punctuation, case-fold, expand common legal-form suffixes
(`pvt`, `private`, `limited`, `ltd`, `llc`, `dmcc`, `pte`, `sdn bhd`, …) only
for *candidate generation*, never for the stored canonical name.

**Proposal workflow** `[PROPOSED]`: whenever R-2/R-3 has no entry, generate a
candidate pair list (token-set similarity, shared domain, shared tax identifier
if ever supplied), present it to a data steward, and store the human decision as
a versioned mapping row. This keeps the automated path deterministic while
letting human judgement improve it over time.

### 6.2 Item resolution `[PROPOSED]`

`Item Name` is free text with embedded structure — observed examples such as

```
Boilersuit-~-MOL-~-StatSafe-Orange -JAP-BM.CL-CT-UV-~-~-2pc
Parka-BM ColdStar-~-N.Blue-Polyster-~-BM.CL-Hooded-Cold Prot-HiViz-WR-- 20° C-~
Safety Shoes-Legasea-Xtreme-Black-PU-Single Density-Leather-StatSafe-O.R-I.R-S.A-Anti Slip-Steel Toe
```

The delimiters are inconsistent (`-~-`, `-`, spaces, `;`), the hierarchy is
implicit, and the trailing token is a pack size (`2pc`) that mixes with colour
and brand. Proposed pipeline:

1. **Parse** on the observed delimiters into `[product family, brand, model,
   attribute…, pack]`, keeping the raw string intact.
2. **Normalise** case, spaces, hyphens, degree symbols, units.
3. **Extract pack size** into its own column so that quantity can be converted
   to a base unit.
4. **Cluster** on the normalised token set; name clusters `item_key`.
5. **Human-confirm** the mapping between `item_family` and the commercial
   category taxonomy that the sales team already uses.

Until step 5 is done, item-family analytics are indicative only.

### 6.3 Data-quality rule catalogue `[PROPOSED]`

Each rule has a code, severity, and blocking behaviour.

| Code | Rule | Severity | On failure |
| --- | --- | --- | --- |
| `DQ-001` | Required columns present with expected names | **Blocker** | Reject the file |
| `DQ-002` | Footer row removed by date regex | **Blocker** | Reject if any footer survives |
| `DQ-003` | `Doc.No.` unique within dataset | **Blocker** | Quarantine duplicates |
| `DQ-004` | Every detail `Doc.No.` has a header | High | Emit finding; keep both |
| `DQ-005` | Σ line `Amount` = header `Amt.Total` (2 dp) | High | Emit finding; flag the document |
| `DQ-006` | Σ line `Qty` = header `Qty Total` | High | Emit finding |
| `DQ-007` | `Grand Total` ≥ `Amt.Total` | Medium | Emit finding |
| `DQ-008` | `Due Date` ≥ `Date` | Medium | Emit finding |
| `DQ-009` | `0 ≤ Outstanding ≤ Grand Total ± tolerance` | Medium | Emit finding, do not auto-correct |
| `DQ-010` | `Qty ≥ 0`, `Rate ≥ 0`, `Amount ≥ 0` | High | Quarantine the row |
| `DQ-011` | Single UoM per item_key | High | Block UoM-blind aggregation |
| `DQ-012` | Customer name resolves to `customer_key` | High | Emit `unverified` flag |
| `DQ-013` | Observed date range within declared range | Medium | Warn loudly |
| `DQ-014` | Rate variance vs trailing median > 50 % | Info | Emit finding for review |
| `DQ-015` | Non-customer placeholders present | Info | Bucket and warn |

`DQ-009` is deliberately a tolerance test, not equality, for the rounding reason
established in §4.9.

---

## 7. Data Flow

### 7.1 End-to-end pipeline `[PROPOSED]`

```mermaid
flowchart LR
    X["ERP exports x4"] --> R["1. Read and hash"]
    R --> V["2. Schema contract check"]
    V --> G["3. Footer strip and typing"]
    G --> Q["4. DQ rules DQ-001..015"]
    Q --> E["5. Entity resolution"]
    E --> S["6. Build star schema snapshot"]
    S --> F["7. Feature store materialisation"]
    F --> M["8. Five analytical modules"]
    M --> W["9. Weighted scoring and ranking"]
    W --> P["10. Recommendation policy"]
    P --> L["11. LLM interpretation"]
    L --> O["12. Schema validation and evidence bind"]
    O --> D["13. Dashboards and exports"]
    W --> D
    Q -.->|"quarantine and alerts"| A["Data steward queue"]
```

Steps 1–7 and 9–10 are **deterministic**. Step 8 is deterministic given
parameters. Only step 11 is non-deterministic, and only in wording — never in
the numbers it is allowed to cite.

### 7.2 Incremental vs full reload `[PROPOSED]`

Given the sample size, **full reload is correct** `[OBSERVED rationale]` — the
entire dataset is ~40 KB of data across 4,395 rows. A full rebuild is
milliseconds and removes an entire class of incremental-correctness bugs. The
production design should still include:

- a `snapshot_id` = `sha256(file_name, file_content, code_version, param_version)`;
- every published metric carries its `snapshot_id`;
- if the content hash is unchanged, the pipeline short-circuits and the previous
  outputs are republished verbatim — which is itself a determinism test.

### 7.3 Scheduling `[PROPOSED]`

| Phase | Trigger | Idempotent |
| --- | --- | --- |
| Ingest + DQ | File-drop watcher or scheduled job | Yes, hash-guarded |
| Rebuild star + features | On new validated snapshot | Yes |
| Run modules | On demand or after rebuild | Yes |
| LLM narrative generation | On demand, cache by `metric_hash` | Yes |
| Publish | After full validation | Yes |

LLM results are cached by `metric_hash`, so re-running the pipeline without a
data change costs zero API calls and produces an identical narrative.

---

## 8. Feature Store

### 8.1 Naming and grain `[PROPOSED]`

Every feature is `(feature_id, entity_type, entity_key, window, value,
as_of_date, snapshot_id)`. `entity_type ∈ {customer, item, order, invoice,
company}`. `window ∈ {7d, 30d, 90d, 180d, 365d, all}`.

### 8.2 Feature catalogue — computable now `[OBSERVED inputs → PROPOSED definitions]`

| Feature ID | Definition | Computable now? |
| --- | --- | --- |
| `f.inv.gross_30d` | Σ `Grand Total` over trailing 30 days | Yes |
| `f.inv.net_30d` | Σ `Amt.Total` over trailing 30 days | Yes |
| `f.inv.count_30d` | Invoice count over trailing 30 days | Yes |
| `f.inv.avg_ticket_30d` | `net_30d / count_30d` | Yes |
| `f.inv.outstanding_total` | Σ `Outstanding Amount` | Yes |
| `f.realisation_rate` | `1 − (Σ outstanding / Σ gross)` | Yes |
| `f.strict_overdue_amt` | Σ outstanding where `terms_days = 0` | Yes |
| `f.overdue_age_max` | Max days past due among term-0 invoices `[ASSUMPTION snapshot date]` | Yes, with confirmed snapshot date |
| `f.tax_rate_effective` | `1 − net/gross` | Yes |
| `f.cust.concentration_share` | Customer gross ÷ company gross | Yes |
| `f.cust.item_breadth` | Distinct `item_key` purchased | Yes (after §6.2) |
| `f.cust.uom_mix` | Share of lines in each UoM | Yes |
| `f.cust.discount_rate` | Σ discount ÷ Σ gross | **No** — discount zero/absent |
| `f.cust.orders_count` | Orders by resolved `customer_key` | Partially — order extract appears filtered |
| `f.cust.otif_rate` | On-time-in-full | **No** — needs delivery data |
| `f.cust.dso` | Days sales outstanding | **No** — needs payment entries |
| `f.cust.days_to_pay_p50` | Median days from invoice to payment | **No** — needs payment entries |
| `f.cust.return_rate` | Returns ÷ invoiced value | **No** — needs returns |
| `f.cust.credit_note_rate` | Credit notes ÷ invoiced value | **No** — needs credit/debit notes |
| `f.cust.region_perf` | Regional revenue and growth | **No** — needs region |
| `f.company.trend_index` | Linear slope on monthly revenue | **Architect only** — 1 month of data |

### 8.3 Illustrative computed values `[OBSERVED]`

| Metric | Value |
| --- | --- |
| Company gross invoiced | 10,829,459.06 |
| Company net invoiced | 10,408,405.39 |
| Company outstanding | 10,352,405.16 |
| Aggregate realisation rate | 4.405 % |
| Invoices with a residual balance | 603 / 610 |
| Invoices fully settled | 7 / 610 |
| Aggregate outstanding as % of gross | 95.595 % |
| Distinct invoiced customers | 33 |
| Top-1 customer share | 46.28 % |
| Top-5 customer share | 76.52 % |
| Top-10 customer share | 90.88 % |
| Distinct items | 182 |
| Top-10 item share | 40.92 % |
| Effective tax rate (invoice) | ~4.045 % of net |

The headline is uncomfortable and should be presented carefully: **4.405 % of
invoiced value has been realised**. Before anyone concludes that the business has
a collections crisis, note §4.10 — 83 % of invoices carry 0-day terms and the
snapshot is a single point in time on a month of activity. The engine's job is
to make exactly this distinction visible, not to hide it behind a number.

---

## 9. Module 1 — Customer Health & Discontinuation Intelligence

### 9.1 Available inputs and honest status

| Sub-capability | Status |
| --- | --- |
| Payment realisation and exposure | **Buildable now** |
| Revenue contribution and concentration | **Buildable now** |
| Order-to-invoice continuity (as proxy for relationship activity) | Buildable, weak — order extract appears filtered |
| Product-mix breadth and drift | Buildable after item resolution |
| Churn / discontinuation prediction | **Architect only** — needs ≥ 12 months |
| Delinquency risk modelling | **Blocked** — needs payment history |

### 9.2 Health score `[PROPOSED]`

All components normalised to 0–100, higher is healthier.

```text
H_realisation = 100 × (1 − outstanding_i / gross_i)
H_commitment  = 100 × (1 − min(1, overdue_share_i / overdue_cap))
H_revenue     = 100 × min(1, gross_i / gross_target_i)
H_diversity   = 100 × (1 − HHI_i)                    # Herfindahl over item mix
H_recency     = 100 × exp(−days_since_last_invoice_i / τ)
H_momentum    = 100 × clamp(0.5 + slope(gross)_i / 2·s_i, 0, 1)

Health_i = Σ_j w_j · H_j(i) / Σ_j w_j
```

with default weights held in configuration:

| Weight | Component | Business meaning |
| --- | --- | --- |
| 0.30 | `H_realisation` | Do they pay? |
| 0.20 | `H_commitment` | Do they respect terms? |
| 0.20 | `H_revenue` | How much do they matter to us? |
| 0.10 | `H_diversity` | Are we their only supplier? |
| 0.10 | `H_recency` | Are they still active? |
| 0.10 | `H_momentum` | Are they growing or shrinking? |

`H_revenue` is deliberately *not* "bigger is better" in isolation — it feeds a
separate exposure metric so that a large delinquent account cannot be hidden by
a healthy weighted average. It is reported alongside `Health`, never instead of
it.

### 9.3 Discontinuation risk `[PROPOSED]`

```text
Risk_i = 100 − Health_i
RiskAdjusted_i = Risk_i × Exposure_i
```

`Exposure_i = gross_i / Σ gross` on the **resolved** customer key, so
concentration enters the risk ranking rather than hiding inside it.

Bands `[PROPOSED]`, to be confirmed by the business:

| Band | Score | Default action |
| --- | --- | --- |
| Critical | 70–100 | Account review within 3 days, senior owner |
| High | 50–70 | Collections contact, credit review |
| Watch | 30–50 | Monitor, proactive outreach |
| Stable | 0–30 | Standard cycle |

### 9.4 Worked example on real data `[OBSERVED inputs, PROPOSED method]`

For `Best Marine Exports` on the delivered sample:

```text
gross_i           = 5,011,852.93
outstanding_i     = 5,011,855.00
H_realisation     = 100 × (1 − 5,011,855.00 / 5,011,852.93) ≈ 0.0
exposure_i        = 5,011,852.93 / 10,829,459.06 = 46.28 %
```

Interpretation the engine would emit: the single largest revenue relationship,
46 % of the business, shows effectively zero realisation on the sample. **But**
this must be presented with its caveats attached — the entity may be `Best
Marine Pvt Ltd Delhi`, which has 477,050.19 invoiced and **zero** outstanding;
`Outstanding` may predate credit notes that were not extracted; and the snapshot
date is unconfirmed. The correct output is therefore *"entity resolution and
snapshot-date confirmation required before escalation"*, not *"customer is a
defaulter"*.

That distinction — flag for verification rather than assert — is a core design
principle of the AI layer (§12).

---

## 10. Module 2 — Sales Bottleneck & Delay Analysis

### 10.1 The intended analysis

```mermaid
flowchart TD
    O["Order booked"] --> A{"Released to<br/>delivery?"}
    A -->|No| B["Release delay"]
    A -->|Yes| C{"Delivered?"}
    C -->|No| D["Delivery delay"]
    C -->|Yes| E{"Invoiced?"}
    E -->|No| F["Billing delay"]
    E -->|Yes| G{"Paid?"}
    G -->|No| H["Collection delay"]
    G -->|Yes| I["Closed"]
    B --> J["Delay ledger"]
    D --> J
    F --> J
    H --> J
    J --> K["Bottleneck ranking by<br/>days and value"]
    K --> L["Root-cause attribution"]
```

### 10.2 What is computable today `[OBSERVED]`

The order→invoice→payment chain is **not linkable** — there is no order
reference on invoices and no order reference on payments because payments do not
exist. What *can* be computed is a data-pipeline and order-side delay analysis:

| Delay type | Proxy available | Status |
| --- | --- | --- |
| Order-entry to line-posting lag | `Posting Date` vs header `Date` on order lines | Buildable for the 32 linked orders |
| Order with no line items | 5 of 37 (§4.6.1) | Buildable — and it is a real finding |
| Order awaiting billing | Order docs with no plausible invoice, by amount and customer | Blocked — no join key, no order status |
| Tax/charge processing delay | Effective tax rate per order | Buildable |
| Invoice ageing | `Due Date`, `Outstanding` | Buildable as a snapshot |
| True delivery delay | — | **Blocked** — no delivery dataset |
| True billing delay | — | **Blocked** — no status timestamps |
| True collection delay | — | **Blocked** — no payment dataset |

### 10.3 Bottleneck output schema `[PROPOSED]`

```json
{
  "bottleneck_id": "BN-ORDER-LINE-MISSING",
  "stage": "order_to_billing",
  "affected_documents": [
    "SO-2526-MH00265-1", "SO-2526-MH00265-2", "SO-2627-AD00007",
    "SO-2627-AD00013", "SO-2627-MH00005"
  ],
  "affected_count": 5,
  "affected_net_value": 285004.12,
  "diagnosis": "suffixing_or_gap",
  "confidence": 0.82,
  "root_cause": "3 documents have lines posted under a -1 suffixed number; 2 have no lines anywhere",
  "recommended_action": "ERP configuration review on sales order document numbering",
  "evidence_metric_ids": ["dq.order_detail_orphan_count", "dq.order_suffix_match_value"]
}
```

Affected net value = 6,120.00 + 6,120.00 + 193,106.00 + 75,570.00 + 4,088.12 =
**285,004.12** `[OBSERVED arithmetic]`.

---

## 11. Modules 3–5 — Regional, Potential, Trends

### 11.1 Module 3 — Regional Sales Intelligence `[BLOCKED on data]`

**Status: cannot be built on the current extract.** No source column in any of
the four sheets carries region, state, country, port, or ship-manager
territory. Deriving region from the customer name is unsafe — `Executive Ship
Management Pte Ltd` is Singapore-incorporated, `Msc Shipmanagement Limited
Cyprus` is Cypriot, and both operate Indian coastal supply. Guessing region from
name would produce a confident, wrong map.

**What to request `[PROPOSED]`**, in priority order:

1. Customer master with billing/shipping address and service region;
2. Sales person / key-account manager with territory;
3. Port or vessel-to-region mapping if route analysis is in scope.

**Design ready to activate `[PROPOSED]`** — once `region` lands on
`customer_dim`, the module computes: revenue and gross margin by region, region
mix shift, region growth vs trailing window, region × product matrix, region
concentration risk (Herfindahl), and "region white space" = regions where
top-decile customers buy categories they do not currently buy.

### 11.2 Module 4 — Customer Potential Analysis

**Status: descriptive only on this sample.**

Available now `[OBSERVED]`:

| Asset | Value |
| --- | --- |
| Distinct items in the invoice detail | 182 |
| Distinct customer strings | 33 |
| Basket shape | Observable per invoice |
| Top-10 item share | 40.92 % |

Proposed potential model:

```text
Affinity(a, i)  = P(item i | customer a) / P(item i | company)
PotentialScore_a = Σ_i ( 1 − P(item i | a) ) · Value_i · Affinity(a, i) · Reach_a
```

Interpretation: for customer `a`, value the items they do **not** buy but
similar customers do buy, weighted by how reachable that expansion plausibly is.

**Honest caveats:**

- `P(item | customer)` computed from **15–20 invoices per customer** is
  statistically very weak. Every affinity must carry a minimum-support guard:
  customers with fewer than *n* observations fall back to segment-level priors
  and the output is labelled `low_confidence`.
- `Affinity` requires ≥ 12 months to mean anything. On one month it describes
  the past, not the opportunity.
- Gross margin is **not available** — there is no cost column in any sheet. So
  potential is ranked on **revenue**, not value. Any business decision that
  turns on profit needs a cost/price master.

### 11.3 Module 5 — Trend & Opportunity Analysis

**Status: architect only.**

With 15 distinct invoice dates spanning 29 calendar days, the platform can
produce a *daily* run-rate and a *within-month* shape. It **cannot** produce:

- month-over-month or year-over-year growth;
- seasonality;
- a statistically meaningful trend slope;
- a demand forecast with any error bar.

Observed daily invoice value does show non-trivial within-month variation —
2026-04-07 alone carries 1,783,224.07 gross, and 2026-04-09/10 carry
1,802,700.47 and 1,587,476.45 — so the dataset does exhibit structure worth
describing. Describing a month's shape is not forecasting.

Proposed feature store design `[PROPOSED]` that becomes live as history accrues:

| Horizon | Minimum history before the metric is published | Metric |
| --- | --- | --- |
| Daily run-rate | 30 days | `Σ gross / distinct_dates` |
| WoW growth | 8 weeks | `(week_t / week_{t-1}) − 1` |
| MoM growth | 3 months | `(month_t / month_{t-1}) − 1` |
| Seasonal index | 24 months | `month_value / mean(month_value)` |
| Trend slope + confidence | 12 months | OLS slope ± CI on monthly revenue |
| Demand signal per item | 12 months, min support 8 weeks | Weighted moving average, item level |

The publication guard is the design point: a metric is **suppressed with an
explicit "insufficient history" message** until its minimum window is met. A
dashboard that quietly shows a forecast built on one month is worse than one
that admits the gap.

---

## 12. Layer 3 — AI Interpretation Layer

### 12.1 Division of labour `[PROPOSED]`

| Question | Answered by |
| --- | --- |
| "What is the outstanding balance?" | Rule engine — exact |
| "Is this customer healthy?" | Rule engine — weighted formula |
| "Which customers are at risk and why?" | Rule engine ranks; **LLM writes the explanation** |
| "What should we do about it?" | Policy table proposes; **LLM phrases and tailors** |
| "How confident are we?" | Rule engine computes the confidence inputs |

The LLM's authority is bounded to: *organise*, *explain*, *prioritise
presentation*, and *draft a message*. It has no authority to compute, rank, or
invent.

### 12.2 Prompt contract `[PROPOSED]`

```text
SYSTEM
  You are the narrative layer of a sales analytics platform.
  You receive a JSON payload of PRE-COMPUTED metrics.
  Rules:
   1. Use ONLY numbers present in the payload. Never derive, round, or estimate.
   2. Every claim MUST cite at least one metric_id from the payload.
   3. If the payload contains "blocked": true, say the analysis is not possible
      and name the missing dataset. Do not estimate.
   4. Do not invent customer names, dates, product names, or causes.
   5. Tone: concise business English. No hedging filler, no apologies.
   6. Respect the audience field: adjust technical depth, not the facts.

USER
  audience: {sales_manager | analyst | executive}
  module:   {customer_health | bottleneck | regional | potential | trend}
  metrics:  <JSON payload>
  template: {insight_summary | risk_card | recommendation | management_review}

OUTPUT — strict JSON, no prose outside the object
  { "headline": str,
    "insight":  str,
    "drivers":  [ {"metric_id": str, "statement": str} ],
    "confidence": { "level": "high|medium|low", "reason": str },
    "recommended_actions": [ {"action": str, "owner": str,
                              "expected_impact": str, "metric_ids": [str]} ],
    "caveats": [str] }
```

### 12.3 Provider gateway `[PROPOSED]`

```mermaid
flowchart LR
    O["Orchestrator"] --> G["LLM Gateway"]
    G --> RT["Router"]
    RT --> N["NVIDIA NIM / free API"]
    RT --> OAI["OpenAI"]
    RT --> CL["Claude"]
    RT --> GE["Gemini"]
    RT --> LL["Local model"]
    RT --> FB["Deterministic fallback"]
    N --> V["Response validator"]
    OAI --> V
    CL --> V
    GE --> V
    LL --> V
    FB --> V
    V --> C["Cache by metric_hash"]
    C --> S["Publish"]
```

Gateway responsibilities, satisfying §9 and §10 of the requirement:

- **Provider abstraction** — one internal `complete(messages, params)` interface
  so NVIDIA-first becomes OpenAI/Claude/local later with a config change only.
- **Model pinning** — the model id is configuration, recorded in every output
  for reproducibility.
- **Temperature discipline** — `temperature = 0` (or the provider's closest
  deterministic setting) for narrative consistency; variation between runs
  should come from data, not from sampling.
- **Retry with backoff**, then **fallback to the deterministic template**.
- **JSON schema validation** of every response; on validation failure, retry
  once with the validation error appended, then fall back.
- **Numeric guard** — a post-response check that every number in the output
  appears in the input payload. This is cheap and catches essentially all
  hallucinated figures.
- **No PII in prompts beyond what the dashboard already shows**, and a
  redaction step for anything not needed.

### 12.4 Deterministic narrative fallback `[PROPOSED]`

Because the requirement (§10) demands consistent output, the fallback is a
first-class code path, not an afterthought:

```python
def render_insight(metrics: dict, template: str) -> str:
    """Deterministic narrative from metrics only. Always available."""
    drivers = sorted(metrics["drivers"], key=lambda d: -abs(d["impact"]))[:3]
    parts = [
        f"{metrics['entity']} shows {metrics['headline_metric']} at "
        f"{metrics['headline_value']}."
    ]
    parts += [f"{d['statement']} (contributes {d['contribution_pct']}%)." for d in drivers]
    if metrics.get("blocked"):
        parts.append(f"Not assessable: missing {', '.join(metrics['missing'])}.")
    return " ".join(parts)
```

The LLM path and the fallback path consume the *same* metric payload, so the
two never disagree on facts — only on prose quality.

### 12.5 Confidence model `[PROPOSED]`

Confidence is **computed, not generated**, and passed to the LLM which must
echo it:

```text
confidence = data_completeness × metric_support × rule_certainty

data_completeness = available_of_datasets_that_this_metric_requires
metric_support    = min(1, n_observations / n_required)
rule_certainty    = 1.0 if a measured fact, else
                  0.7 if an inferred relationship, else
                  0.4 if a heuristic

bands: high ≥ 0.70 | medium ≥ 0.40 | low ≥ 0.20 | blocked if data_completeness = 0
```

`data_completeness` is deliberately **metric-relative**, not company-wide. A
global "3 of 8 datasets present" denominator would drag every metric down and
teach users to ignore the score. Realisation rate needs only invoices, and the
invoice extract reconciles perfectly, so its confidence is genuinely high. The
missing datasets belong in a separate, honest statement — the module
availability matrix in §14.3 — not in the denominator of a metric that does not
need them.

Evaluated on the delivered sample:

| Output | Datasets required | Available | Support | Certainty | Score | Level |
| --- | --- | --- | --- | --- | --- | --- |
| Realisation rate | invoice header | 1 / 1 | 610 / 30 | 1.0 | 1.00 | **high** |
| Outstanding exposure | invoice header | 1 / 1 | 610 / 30 | 1.0 | 1.00 | **high** |
| Concentration risk | invoice header | 1 / 1 | 33 / 20 | 1.0 | 1.00 | **high** |
| Order bottleneck | order header + detail | 2 / 2 | 32 / 37 | 1.0 | 0.86 | **medium** |
| Customer potential | invoice detail + item master | 1 / 2 | 33 / 50 | 0.7 | 0.23 | **low** |
| Churn prediction | invoices + payments + ≥ 12 months | 1 / 3 | 1 / 12 months | 0.4 | 0.01 | **suppressed** |
| Regional analysis | region field | 0 / 1 | — | — | 0.00 | **blocked** |
| DSO | payment entries | 0 / 1 | — | — | 0.00 | **blocked** |

Note the two distinct failure modes at the bottom of the table. `suppressed`
means the data exists but is too thin to support the claim. `blocked` means the
data does not exist at all. They need different remediation and different
owners, so the platform reports them differently.

Surfacing `blocked` with `confidence = 0` is a feature, not a gap: it is what
stops the platform from confidently answering questions the data cannot answer.

---

## 13. Recommendation Engine

```mermaid
flowchart TD
    S["Ranked signals from modules"] --> P{"Policy match"}
    P --> PS["Strict overdue<br/>over threshold"]
    P --> PH["High-risk exposure"]
    P --> PP["Potential expansion"]
    P --> PB["Bottleneck detected"]
    P --> PT["Trend anomaly"]
    PS --> PR["Priority score"]
    PH --> PR
    PP --> PR
    PB --> PR
    PT --> PR
    PR --> A["Action with owner,<br/>expected value, due date"]
    A --> L["LLM phrases and tailors<br/>the action text"]
    L --> H["Human review for<br/>high-impact actions"]
```

Priority `[PROPOSED]`:

```text
Priority = severity × exposure × urgency × (1 / effort)
```

All four factors come from configuration. Actions with
`exposure × severity` above a threshold are queued for **human approval before
execution** — the platform recommends; people with authority decide.

Action catalogue `[PROPOSED]`, each tied to a trigger and an owner:

| Trigger | Recommended action | Default owner |
| --- | --- | --- |
| `strict_overdue_amt` > 0 and days past due > 14 | Collections contact within 5 working days | AR |
| `realisation_rate` < 0.5 and `exposure` > 10 % | Credit limit / prepayment review | Finance + Sales head |
| Entity resolution conflict on a > 10 % customer | Confirm legal entity and credit terms before any escalation | Data steward |
| Order with no lines > 7 days | ERP document-numbering review | ERP / IT |
| Item affinity gap above threshold | Structured cross-sell outreach | Key account manager |
| Region white space (when available) | Territory expansion proposal | Sales head |
| Insight confidence < 0.4 | Do not publish; route to analyst queue | Analyst |

---

## 14. Output Contracts

### 14.1 Customer risk card `[PROPOSED]`

```json
{
  "snapshot_id": "sha256:…",
  "param_version": "params-1.3.0",
  "customer_key": 42,
  "customer_name_canonical": "Best Marine Exports",
  "entity_resolution": {
    "state": "needs_review",
    "member_strings": ["Best Marine Exports", "Best Marine Online",
                       "Best Marine Pvt Ltd Delhi"],
    "reason": "alias mapping unconfirmed for group membership"
  },
  "health_score": 32.3,
  "risk_score": 67.7,
  "risk_band": "high",
  "exposure_pct": 46.28,
  "components": {
    "realisation": 0.0,
    "commitment": 0.0,
    "revenue": 100.0,
    "diversity": 61.4,
    "recency": 12.0,
    "momentum": 50.0
  },
  "metrics": {
    "gross_30d": 5011852.93,
    "outstanding_total": 5011855.0,
    "realisation_rate": -0.00000041,
    "invoice_count": 20
  },
  "confidence": {
    "level": "high",
    "data_completeness": 1.0,
    "metric_support": 1.0,
    "rule_certainty": 1.0,
    "scope": "confidence applies to the measured figures only, not to entity identity",
    "reason": "all figures derive from a fully reconciled invoice extract; entity grouping is unresolved"
  },
  "drivers": [
    {"metric_id": "f.realisation_rate", "impact": -0.30},
    {"metric_id": "f.cust.concentration_share", "impact": -0.15}
  ],
  "recommended_actions": [
    {"action": "Confirm legal entity and credit terms before collections action",
     "owner": "Data steward + AR",
     "metric_ids": ["f.inv.outstanding_total", "f.cust.concentration_share"]}
  ],
  "caveats": [
    "Outstanding exceeds invoiced gross by 2.07 due to source rounding granularity.",
    "Entity group membership is unconfirmed; group-level outstanding is 5036591.00.",
    "Snapshot date is inferred from file name, not asserted by the data."
  ]
}
```

Note what the contract does: it reports the alarming number, the entity doubt,
and the rounding artefact **together**. A weaker design would show the score
alone and the reader would act on a number that may belong to the wrong entity.

The score above is arithmetically self-consistent with §9.2, so a reviewer can
check it: `health = (0.30·0.0 + 0.20·0.0 + 0.20·100.0 + 0.10·61.4 + 0.10·12.0 +
0.10·50.0) / 1.00 = 32.34`, giving `risk = 67.66` and band `high` under the
§9.3 banding. The `momentum` component is a placeholder at its neutral value of
50 because a slope on one month of data would be meaningless — another example
of the platform declining to publish a number it cannot support.

### 14.2 Management review summary `[PROPOSED]`

Consists of: period, snapshot and parameter provenance; data-completeness
banner; revenue and realisation headline; concentration warning; top-5 risks;
top-5 opportunities; module availability matrix; data-quality findings that
gated the numbers; and an explicit list of what could **not** be analysed and
what data would unblock it.

### 14.3 Module availability matrix `[OBSERVED assessment]`

| Module | Status | Blocking gap |
| --- | --- | --- |
| Customer Health | Live | — |
| Discontinuation prediction | Suppressed | ≥ 12 months history |
| Order / billing bottleneck | Live (partial) | Order status timestamps |
| Delivery bottleneck | Blocked | Delivery / GRN dataset |
| Collection bottleneck | Blocked | Payment entries |
| Regional sales | Blocked | Region or territory field |
| Customer potential | Live (descriptive) | Item master, cost data, 12 months |
| Trend & opportunity | Suppressed | ≥ 12 months history |
| Returns / credit notes | Blocked | Return, credit note, debit note datasets |
| Customer master attributes | Blocked | Customer master table |

---

## 15. Technology Choices and Trade-offs

| Layer | Choice `[PROPOSED]` | Alternative | Trade-off |
| --- | --- | --- | --- |
| Ingestion | Python + pandas + openpyxl | Power Query, Airbyte | Already implied by the ERP's Excel outputs; lowest friction |
| Storage (POC) | DuckDB + Parquet | PostgreSQL | Analytical, zero-server, file-based; trivial to hand over |
| Storage (prod) | PostgreSQL | Snowflake, BigQuery | Managed scale once multi-user and concurrent writes appear |
| Transformation | pandas or DuckDB SQL | dbt, Spark | dbt adds lineage and tests at the cost of setup |
| Orchestration | Dagster or Prefect | Airflow | Data-quality gates as first-class steps |
| Rule engine | Config-driven Python + YAML weights | Drools, DMN | Transparent to the business; no new DSL to learn |
| LLM gateway | Thin provider-abstraction client | LangChain, LlamaIndex | A gateway is ~200 lines; frameworks add dependency risk |
| Model host | NVIDIA API first | local vLLM | Meets §9; swap later via config |
| Serving | FastAPI REST + static JSON export | Streamlit | Separates compute from presentation |
| Dashboard | Power BI / Metabase over the star schema | React + D3 | Business already knows Power BI; no new skill |
| Validation | pytest + golden JSON fixtures + snapshot diffs | manual review | Directly proves the §10 consistency requirement |
| Config | YAML in version control | database-driven config | Diffable, reviewable, auditable |

**Deliberate non-choices `[PROPOSED]`:**

- **No vector database and no RAG over the transactions.** The insight is
  arithmetic plus explanation. Retrieval adds cost, non-determinism and a second
  place for errors, with no benefit at this data scale. If narrative documents
  (contracts, product specs, sales policies) are later added, that is when RAG
  belongs — in the interpretation layer only.
- **No fine-tuning in the POC.** §10 demands repeatability; a pinned prompt and
  schema validation deliver that. Fine-tuning adds a training set, a drift
  problem and a reproducibility problem.
- **No microservice split.** Four layers, one deployable pipeline, one serving
  app. Microservices are an answer to scale this project does not have.

---

## 16. Testing & Validation Strategy

This section is how the POC proves §10 "Consistency & Reliability" rather than
merely claiming it.

### 16.1 Test layers `[PROPOSED]`

| Layer | What is asserted | Gate |
| --- | --- | --- |
| Unit | DQ rule functions, weight arithmetic, band boundaries, normalisation | Blocks merge |
| Contract | Each source file still matches its YAML schema contract | Blocks publish |
| Reconciliation | Σ lines = header; orphan detection; UoM consistency | Blocks publish |
| Golden output | Full metric payload byte-matches a committed fixture | Blocks publish |
| Determinism | Same snapshot + same params → identical payload across 5 runs | Blocks publish |
| Snapshot diff | New run differs from previous only in expected metrics | Requires sign-off |
| LLM contract | Response parses; every number exists in the input; schema valid | Blocks publish of that insight |
| Fallback | With the LLM disabled, every insight still renders | Blocks publish |
| Business acceptance | Analyst reconciles top-10 numbers to the Excel by hand | Sign-off |

### 16.2 Known reconciliation results to encode as tests `[OBSERVED]`

These are real, currently-observed facts. They are excellent regression fixtures
because they are non-trivial and hand-verifiable:

1. Invoice rows after footer strip = **610**.
2. Invoice header ↔ detail document match = **610 / 610**.
3. Invoice line-sum vs header net = **610 / 610 exact**.
4. Invoice line-sum qty vs header qty = **610 / 610 exact**.
5. Order rows after footer strip = **37**; order detail documents = **32**.
6. Orphan orders = **5**, of which **2** have an exactly-matching `-1` twin.
7. Company net invoiced = **10,408,405.39**; gross = **10,829,459.06**.
8. Company outstanding = **10,352,405.16**.
9. Order net = **4,549,969.80**; gross = **5,106,918.32**; tax = **556,948.52**.
10. Distinct invoice customers = **33**; order customers = **12**; overlap = **7**.
11. Distinct items = **182**.
12. UoM split = 2,664 `Nos` lines / 669 `Pair` lines.
13. `Cash Sale` = 75 invoices / 133,391.69 gross.
14. Max invoice date = **30-Apr-2026** even though file names declare 16-May-2026.

### 16.3 Acceptance criteria `[PROPOSED]`

The POC succeeds when:

1. `pytest` and the golden-output suite pass on a clean checkout.
2. The same input produces byte-identical metric payloads across five runs.
3. Every published number traces to a `snapshot_id`, a parameter version and a
   list of contributing `metric_id`s.
4. Disabling the LLM still produces a complete, correct dashboard.
5. The module availability matrix (§14.3) is displayed and truthful.
6. An analyst has hand-reconciled the top-10 customers, top-10 items and the
   five orphan orders to the source workbooks.
7. Every "blocked" analysis states the missing dataset by name.

---

## 17. Delivery Plan

Durations are indicative effort for a small team and should be re-estimated with
the client's own capacity `[PROPOSED]`.

| Phase | Scope | Exit criteria |
| --- | --- | --- |
| **P0 — Data foundation** | Contracts, reader, footer handling, DQ rules, star schema, entity resolution for the observed strings | 610/37 row reconciliation passes; 5 orphans explained; golden tests green |
| **P1 — Rule engine** | Feature store, Customer Health, Bottleneck analysis, availability matrix | Scores reproducible; weights configurable without code change |
| **P2 — Interpretation** | LLM gateway, prompt registry, schema validation, numeric guard, deterministic fallback | Insights validate; fallback covers 100 % of outputs; 3 repeated runs agree on all cited numbers |
| **P3 — Presentation** | Dashboards, risk cards, recommendation panel, exports, management summary | Stakeholder walkthrough signed off |
| **P4 — Hardening** | Determinism suite, snapshot diffs, logging, alerting on DQ | §16.3 all satisfied |
| **P5 — Extension** *(conditional)* | Regional module, potential model hardening, trend metrics as history accrues | Blocked until the corresponding dataset lands |

Critical path is P0 → P1 → P2 → P3. P4 cannot be compressed: a platform whose
selling point is "repeatable, explainable output" and which cannot prove
repeatability has not met the requirement.

---

## 18. Data Requests to the Client `[PROPOSED]`

Ordered by analytical value unlocked per unit of effort:

| Priority | Request | Unblocks |
| --- | --- | --- |
| 1 | **Payment entries / receipts** (invoice ref, receipt date, amount, mode) | DSO, days-to-pay, real delinquency, genuine churn signals |
| 2 | **Customer master** (code, legal name, group, segment, credit limit, terms, address, region, salesperson) | Entity resolution confidence, region module, credit-aware health |
| 3 | **Sales order ↔ invoice linkage** (order ref on the invoice, or an order status table) | True order-to-cash funnel, billing delay, conversion |
| 4 | **Delivery / GRN records** | OTIF, delivery bottleneck, true lead time |
| 5 | **Returns, credit notes, debit notes** | Net revenue, return rate, quality-driven churn |
| 6 | **Item master** (code, family, cost, UoM, pack size) | Margin-aware potential, correct quantity maths |
| 7 | **≥ 24 months of history** | All trend, seasonality and forecast capability |
| 8 | Confirmation of the **outstanding snapshot date** and whether it is pre- or post-credit-note | Correctness of every ageing metric |
| 9 | Explanation of the **`SO-2526-MH00265-1/-2`** duplicate pair | Completeness of order analysis |
| 10 | Definition of **payment terms** (is 0-day "due on receipt"?) | Correctness of overdue logic |

Items 8, 9 and 10 cost one email each and materially change published numbers.
They should be asked before P1 exit review, not after.

---

## 19. Risks and Limitations

| # | Risk | Severity | Mitigation |
| --- | --- | --- | --- |
| R1 | One month of data validated as a "trend and opportunity" platform | **High** | Suppress under-powered metrics with explicit messages; agree the reduced POC scope in writing before build |
| R2 | No payment data, yet the requirement is Order-to-Cash | **High** | Ship Order-to-Invoice honestly; publish the availability matrix; request item 1 |
| R3 | Customer fragmentation corrupts every customer-level metric | **High** | Entity resolution in P0; `unverified` flag; no customer score without a `customer_key` |
| R4 | The order export appears filtered, so order-side metrics may be wrong | High | Confirm extract filter with the client; label order metrics `partial` until confirmed |
| R5 | Mixed UoM silently corrupts quantity metrics | Medium | UoM-aware feature layer; `DQ-011` |
| R6 | `Grand Total` vs `Amt.Total` confusion produces wrong comparisons | Medium | Every metric declares its basis; gross for cash, net for performance |
| R7 | Outstanding > gross on some documents looks like an error and invites distrust | Medium | Document the derivation artefact in the methodology note (§4.9) |
| R8 | LLM invents a number and a user acts on it | **High** | Numeric guard, schema validation, evidence binding, deterministic fallback |
| R9 | Prompt or model change silently alters published narratives | Medium | Pin prompt version and model id in config; store both with every output; snapshot-diff narratives too |
| R10 | Free API rate limits or outage mid-demo | Medium | Cache by `metric_hash`, retry with backoff, deterministic fallback |
| R11 | Scope creep into 13 "future scope possibilities" | Medium | Future scope is out of the POC; P5 only, and only when data lands |
| R12 | Executives ask for a customer risk score and read it as fact | **High** | Score cards always carry confidence, caveats and the availability matrix; make caveats impossible to hide in the UI |
| R13 | Entity group assumption (Best Marine) is wrong | High | Surface as `needs_review`; never auto-merge; require steward sign-off |
| R14 | Single-customer concentration means one lost account dominates every metric | Medium | Always report with and without the top customer |

---

## 20. Interview Questions & Model Answers

**Q1. Walk me through this project end to end.**
Four Excel exports land in a drop folder. We validate them against declared schema contracts, strip the `Grand Total` footers, and run fifteen data-quality rules. Anything that fails is quarantined and raised as a finding rather than silently fixed. Surviving rows go through entity resolution, where raw customer strings become governed customer keys — this is critical because the order and invoice exports share only seven of their customer names. We build a conformed star schema plus a snapshot id that fingerprints the exact inputs, code and parameters. A deterministic rule engine then computes every metric and runs the five analytical modules. A weighted, parameter-driven scoring model ranks customers and generates signals. A policy table turns signals into actions. Only then does an LLM enter: it receives a JSON payload of pre-computed metrics and may only organise, explain and phrase them — never calculate. Its output is schema-validated, every number is checked to exist in the input, and if anything fails a deterministic template renderer produces the narrative from the same payload. Finally the visualization layer publishes dashboards, risk cards, recommendation panels and exports.

**Q2. How do you guarantee the AI gives consistent answers?**
Three mechanisms. First, the LLM performs no arithmetic — all numbers come from the rule engine, so consistency of figures is a property of deterministic code, not of a language model. Second, prompts are versioned in a registry and the model id plus temperature are pinned in configuration and recorded with every output. Third, there is a deterministic fallback renderer: if the model is unavailable, times out, or returns invalid output, a template generator produces the explanation from the same metric payload. I enforce this with a test that runs the whole pipeline five times and asserts byte-identical metric payloads, plus a test that disables the LLM entirely and asserts the dashboard still renders completely.

**Q3. Why not use LangChain, a vector database and RAG?**
The insight here is arithmetic plus explanation, not retrieval. Four workbooks of forty thousand rows of transactional data answer every question through aggregation — a vector store would add cost, latency and a second failure mode for zero analytical benefit. LangChain would add a large dependency surface to a gateway that is roughly two hundred lines of provider-abstraction code. If narrative documents such as contracts, product specifications or sales policies are added later, retrieval becomes valuable — but then it belongs in the interpretation layer, not in the metric computation.

**Q4. What did you find in the data that the client probably did not know?**
Several things. Every workbook carries a `Grand Total` footer row that inflates any naive sum by one row. The invoice export is internally perfect — 610 documents, and every document's line amounts and quantities sum exactly to its header. The order export is not — five orders have no lines, and for two of them the lines exist but were posted under a `-1` suffixed document number with identical value and quantity. That is a 268,676 net value of order activity that a naive join would report as missing. Most importantly, the order and invoice exports share only seven customer names: 33 in the invoices, 12 in the orders, with 26 invoice-only and 5 order-only. And three invoice customer strings that look like one group account for 50.9 % of invoiced value. So customer-level analytics are only as good as the entity resolution, and that became the first build phase rather than a cleanup task.

**Q5. You say 95.6 % of invoiced value is outstanding. Isn't that alarming?**
It is a striking number and I would not present it without three caveats. First, 83 % of invoices carry 0-day terms, so any residual balance is already past due — which makes the figure real rather than an artefact of unexpired terms. Second, the snapshot date is not stated in the data; I inferred mid-May from the file names, which is an assumption, not a fact. Third, and most importantly, `Best Marine Pvt Ltd Delhi` is fully settled while `Best Marine Exports` is fully outstanding — if those are one customer group on one commercial arrangement, the picture changes completely. This is exactly why the platform reports a confidence level and a `needs_review` entity state instead of a bare risk score. The right output is "verify the entity and the snapshot date before escalating", not "this customer is a defaulter".

**Q6. How would you validate an AI-driven analytics platform?**
With the same rigour as code. Data-quality tests assert the reconciliation numbers — 610 of 610 invoice documents match, 32 of 37 orders match. Golden-output fixtures assert the full metric payload. A determinism test asserts five runs produce identical payloads. An LLM contract test asserts the response parses, matches the schema, and cites only numbers present in the input. A fallback test asserts the dashboard is complete with the LLM disabled. And a business acceptance test where an analyst hand-reconciles the top ten customers and the five orphan orders against Excel. The last one is the only test that proves the numbers are *right* rather than merely repeatable.

**Q7. What is the biggest technical risk, and how do you mitigate it?**
The largest risk is producing a confident, wrong customer risk score because of customer-name fragmentation — the data supports it, since 50 % of revenue sits behind three strings that may or may not be one entity. Mitigation is structural: entity resolution is phase zero, every customer-level metric requires a resolved key, unverified entities are flagged rather than scored silently, and no auto-merge happens without human sign-off. The second risk is LLM hallucinated figures, mitigated by the numeric guard, schema validation, evidence binding and deterministic fallback. The third is scope: the requirement asks for Order-to-Cash with five modules, but the data supports Order-to-Invoice with about two and a half. I would resolve that in writing before building, not discover it at the acceptance review.

**Q8. How does this scale?**
POC scale is already trivial — the full dataset is forty thousand rows and a full rebuild is milliseconds, so the POC does a complete reload with no incremental logic, which removes a whole class of correctness bugs. For production I would swap DuckDB and Parquet for PostgreSQL behind the same star schema, keep the rule engine pure so it is testable in isolation, put the LLM gateway behind a queue so a long narrative never blocks a pipeline run, cache generations by metric hash so re-runs cost nothing, and add a customer master and payments as new sources — which is an additive change to the ingestion layer only. The layers that carry the business logic do not change.

**Q9. What would you do in the first two weeks?**
Confirm the data. Specifically: get the outstanding snapshot date and whether it is pre- or post-credit-note; ask what "0-day" payment terms means; ask why `SO-2526-MH00265-1` and `-2` are identical with no lines; get the customer master; confirm whether the order export is filtered. Then build the ingestion contract and data-quality gate and encode the fourteen reconciliation assertions as tests. The value of the first fortnight is not a dashboard — it is knowing exactly which numbers can be published and which must be labelled blocked, with evidence.

**Q10. What is explicitly out of scope?**
Forecasting, churn prediction, demand prediction, a conversational assistant and automated alerts — all listed under future scope in the requirement. Also out of scope: margin analysis, because there is no cost data; anything regional, because there is no region field; anything about delivery or returns, because those datasets are absent; and microservice decomposition, a vector database and RAG, none of which this scale justifies. Naming what is out of scope is how the consistency requirement in section 10 of the requirement actually gets met.

---

## 21. Appendix A — Source Index

| Artefact | Path | Use in this document |
| --- | --- | --- |
| Requirement document | `HNS/AI_Sales_Analytics_POC_Requirement_Document.docx` | §1.1, §2, §12, §15, §20 — all `[REQUIRED]` items |
| Invoice header extract | `HNS/Sales Invoice - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16_Sales Invoice_Submitted + Draft_Date Wise Sales Invoice.xlsx` | §4.2, §8.3, §9.4 |
| Invoice detail extract | `HNS/Sales Invoice Details - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16_Sales Invoice_Submitted + Draft__Date Wise Sales Invoice.xlsx` | §4.3, §4.7.1, §4.8, §4.11 |
| Order header extract | `HNS/Sales Order - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16_Date Wise Sales Order.xlsx` | §4.4, §4.12 |
| Order detail extract | `HNS/Sales Order Details - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16__Submitted + Draft_Date Wise Sales Order.xlsx` | §4.5, §4.6, §4.6.1 |

Every worksheet is named `Query Report`. All figures in §4, §8.3, §9.4, §10.3 and §16.2 are reproducible
from these five files.

---

## 22. Appendix B — Observed Figures, Consolidated

| Figure | Value | Source |
| --- | --- | --- |
| Invoice data rows (footer removed) | 610 | invoice header |
| Invoice line rows | 3,333 | invoice detail |
| Order data rows (footer removed) | 37 | order header |
| Order line rows | 415 | order detail |
| Invoice documents matched to lines | 610 / 610 | reconciliation |
| Order documents matched to lines | 32 / 37 | reconciliation |
| Orphan orders | 5 | §4.6.1 |
| Orphan orders with a matching `-1` twin | 2 | §4.6.1 |
| Orphan order net value | 285,004.12 | §4.6.1 |
| Invoice net value | 10,408,405.39 | invoice header |
| Invoice gross value | 10,829,459.06 | invoice header |
| Invoice outstanding | 10,352,405.16 | invoice header |
| Aggregate outstanding / gross | 95.595 % | derived |
| Aggregate realisation rate | 4.405 % | derived |
| Invoices with residual balance | 603 / 610 | invoice header |
| Invoices fully settled | 7 / 610 | invoice header |
| Invoice quantity total | 14,998 | invoice header (mixed UoM) |
| Order net value | 4,549,969.80 | order header |
| Order gross value | 5,106,918.32 | order header |
| Order taxes / charges | 556,948.52 | order header |
| Order quantity total | 6,860 | order header (mixed UoM) |
| Invoice customers (raw strings) | 33 | invoice header |
| Order customers (raw strings) | 12 | order header |
| Customers in both exports | 7 | cross-export |
| Best Marine group value | 5,513,638.57 | invoice header |
| Best Marine group share | 50.91 % | derived |
| Top-1 customer share | 46.28 % | derived |
| Top-5 customer share | 76.52 % | derived |
| Top-10 customer share | 90.88 % | derived |
| Distinct items | 182 | invoice detail |
| Top-1 item share | 11.13 % | invoice detail |
| Top-10 item share | 40.92 % | invoice detail |
| UoM `Nos` lines | 2,664 | invoice detail |
| UoM `Pair` lines | 669 | invoice detail |
| `Cash Sale` invoices / gross | 75 / 133,391.69 | invoice header |
| Payment terms 0 / 4 / 30 days | 507 / 2 / 101 | invoice header |
| Invoice date range (data) | 02-Apr-2026 → 30-Apr-2026 | invoice header |
| Order date range (data) | 01-Apr-2026 → 29-Apr-2026 | order header |
| Date range (file names) | 01-Apr-2026 → 16-May-2026 | file names |
| Order discount | 0.00 on all 37 rows | order header |
| Distinct order dates / invoice dates | 12 / 15 | both headers |

---

*End of document.*


---

## Part II: ERP AI Analytics Implementation Deep-Dive

*Reproduced verbatim from `PROJECT_FLOW.md` (2,109 lines).*

---

# ERP AI Analytics (erp-bot) - AI Sales Intelligence Chatbot

Project Flow, Architecture and Engineering Design Document

**Project code:** erp-bot
**Repository:** `https://github.com/nachiiiket/erp-bot.git` (branch `main`)
**Document type:** Project flow / architecture / design specification
**Document version:** 1.0
**Status:** Describes a **running, deployed** codebase (implemented system, not a proposal)
**Live deployment:** `https://erp-2w694uaqf-erp-bot-demo.vercel.app/`

---

## 0. How To Read This Document

This document describes **erp-bot**: a deployed, end-to-end AI sales analytics
chatbot. Unlike a design specification, every architecture, algorithm and
workflow described here exists as executable code in the repository. The
document is therefore an *analysis of an implemented system* - what it does,
how it does it, what it gets right, and where it is wrong.

So that a reviewer can always separate evidence from interpretation, every
statement in a heading or table caption carries a tag:

| Tag | Meaning |
| --- | --- |
| `[IMPLEMENTED]` | Present in the source code. Path and line range are given and reproducible. |
| `[VERIFIED]` | Executed against the real data in `data/` during preparation of this document. The exact output is quoted. |
| `[OBSERVED]` | Read directly from repository artefacts (source, git history, config, data files). Not executed. |
| `[DESIGN]` | An interpretation or rationale for why the code is shaped this way. Inference, not stated by the author. |
| `[GAP]` | A requirement or behaviour that is missing, incomplete, or contradicted by the code. |
| `[RISK]` | A defect, security exposure, or correctness hazard, with a demonstrated trigger. |
| `[BLOCKED]` | Cannot be verified from this repository alone (external service, secret, or runtime dependency). |

Anything without a tag in a heading or table caption should be read as
`[IMPLEMENTED]` narrative backed by the cited source lines.

**Verification environment.** All `[VERIFIED]` figures were produced with
Python 3.10.11, pandas 2.3.3, numpy 2.2.6 on Windows, importing
`llm_api.data_loader` and `llm_api.analytics_tools` directly. The Django and
OpenAI layers were **not** executed (see `14. Risks and Limitations`).

---

## 1. Executive Summary

### 1.1 What this project is `[IMPLEMENTED]`

erp-bot is a natural-language chatbot over ERP sales data. A user opens a web
page, pastes an access token, and asks questions in plain English:

> *"Which products and customers should we discontinue and why?"*

A Django REST endpoint accepts the question, hands it to an LLM agent
(NVIDIA Nemotron by default), lets the model call **12 deterministic Python
analytics tools** in a loop, and returns a structured answer
(`Summary -> Key Findings -> Recommendations`) with badges showing which tools
were used.

The essential architectural bet is:

> **The model never computes. It only selects tools and narrates their output.**

All arithmetic happens in pandas. The LLM is restricted to (a) choosing a
tool, (b) choosing its arguments, and (c) turning the returned JSON into
prose. This is what makes the numbers trustworthy and the answers
reproducible in structure, even though the prose is not byte-reproducible.

### 1.2 What actually exists `[OBSERVED]`

| Component | Reality | Evidence |
| --- | --- | --- |
| Frontend | Single-file vanilla HTML/CSS/JS, 917 lines | `index.html` |
| Backend | Django 5.2.7 + Django REST Framework | `requirements.txt` |
| Agent | OpenAI-compatible client, 6-iteration tool loop | `agent.py:231-305` |
| Analytics | 12 registered pandas tools, 529 lines | `analytics_tools.py:516-529` |
| Data | 4 Excel workbooks, 211,365 bytes, committed | `data/` |
| Persistence | **None.** `models.py` is 2 lines, empty | `llm_api/models.py` |
| Deployment | Vercel serverless WSGI, catch-all rewrite | `vercel.json`, `app.py` |
| Tests | `tests.py` is the untouched Django stub | `llm_api/tests.py` |
| Git | 16 commits, working tree clean, 34 tracked files | `git log`, `git status`, `git ls-files` |

Total application source (excluding the HTML/CSS shell): **~1,070 lines of
Python** across the five substantive `llm_api` modules - `agent.py` 305,
`analytics_tools.py` 529, `views.py` 142, `data_loader.py` 89, `urls.py` 8.

### 1.3 The three findings that shape this document

1. **The invoice header workbook is shipped but never read.**
   `data/` contains four exports. `DATA_FILES` maps only three of them
   (`data_loader.py:17-30`). The file with `Outstanding Amount` and `Due Date`
   - i.e. every field needed for payment, DSO and overdue analysis - is
   present on disk, tracked in git, and **loaded by zero lines of code**.
   Consequently two tools return `DATA_NOT_AVAILABLE` stubs and the health
   score has no payment dimension at all.

2. **Order-to-invoice analysis joins on customer name and produces
   numbers up to 4.94 x 10^17.**
   There is no order-to-invoice key. The tool outer-joins two customer-name
   aggregates (`analytics_tools.py:296-302`) and then divides by
   `so_revenue + 1e-9` (`:304`). For the 26 customers who appear in invoices
   but in no order export, `so_revenue = 0` and the denominator collapses to
   `1e-9`. Result: `gap_pct = -4.94287053e+17`, `status = OVER_INVOICED`,
   and **31 of 38 rows have an empty join side** (26 invoice-only, 5
   order-only). Only 7 rows have data on both sides, and **just 1 of those
   is `MATCHED`.**

3. **The same customer gets two contradictory trend labels.**
   `get_trend_direction` zero-fills the week axis before fitting, and drops
   `STABLE` entities from its response. `get_customer_deep_dive` does *not*
   zero-fill. For `V.Ships India Pvt.Ltd.` the first tool returns **nothing**
   (classified `STABLE`, silently omitted) while the second returns
   **`trend: DECLINING`** with the action *"Declining activity - investigate
   satisfaction, pending orders, or competitive loss."* Both call the same
   `_slope_label` on differently-shaped input.

### 1.4 Verified baseline at a glance `[VERIFIED]`

All figures below were reproduced by executing the repository's own code.

| Metric | Value |
| --- | --- |
| Loaded frames | `so` 37 x 10, `sod` 415 x 13, `inv` 3333 x 13 |
| Invoice net revenue (`inv['Amount'].sum()`) | 10,408,405.39 |
| Invoice quantity | 14,998 |
| Invoice documents (`Doc.No.` nunique) | 610 |
| Distinct invoice customers | 33 |
| Distinct invoice items | 182 |
| Derived categories | 46 |
| Sales-order gross (`so['Grand Total'].sum()`) | 5,106,918.32 |
| Sales-order net (`so['Amt.Total'].sum()`) | 4,549,969.80 |
| Sales-order detail net (`sod['Amount'].sum()`) | 4,264,965.68 |
| Order net minus order-detail net (orphan orders) | 285,004.12 |
| Invoice weeks present (ISO) | 14, 15, 16, 18 |
| Sales-order weeks present (ISO) | 14, 15, 16, 18, 19 |
| Derived `category` count | 46 |
| Tools registered | 12 (10 computing, 2 stubs) |
| Agent iteration cap | 6 |
| Session history cap | 20 messages (10 exchanges) |

### 1.5 Position relative to the HNS requirement document `[GAP]`

This repository is the working POC against the HNS requirement document
*"AI-Based Sales Analytics & Decision Intelligence Platform"*. The lineage is
visible in the code itself: `settings.py:188` still carries the comment
*"Local frontend support for hns_agent.html"*, and the agent's system prompt
names the business (*"Best Marine Private Limited"*).

Section `2. Requirement Traceability` maps each required module to its actual
implementation status. In short: **2 of 5 modules partially implemented,
3 of 5 not implemented, and no module emits the required confidence levels.**

---

## 2. Requirement Traceability `[REQUIRED] -> [IMPLEMENTED]`

| # | Requirement (HNS document) | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Module 1 - Customer Health & Discontinuation Intelligence | **PARTIAL** | `get_customer_health_scores`, `get_discontinuation_candidates` exist. No payment component; no confidence field. |
| 2 | Module 2 - Sales Bottleneck & Delay Analysis | **MISSING** | 0 occurrences of `bottleneck`/`delivery` in `*.py`. Needs delivery/PO data not present. |
| 3 | Module 3 - Regional Sales Intelligence | **MISSING** | 0 occurrences of `region`/`regional` in `*.py`. No region column in any workbook. |
| 4 | Module 4 - Customer Potential Analysis | **MISSING** | 0 occurrences of `potential` in `*.py`. |
| 5 | Module 5 - Trend & Opportunity Analysis | **PARTIAL** | `get_trend_direction`, `get_volume_growth_alerts`. But see defects F-03, F-05. |
| 6 | Full Order-to-Cash lifecycle | **PARTIAL** | Orders + invoices only. Delivery, payments, credit/debit notes absent. Returns is a stub. |
| 7 | Explanations, justifications, supporting parameters | **PARTIAL** | Free-text `reason` / `action` / `recommendation` strings only; no structured parameter list. |
| 8 | Confidence levels | **MISSING** | 0 occurrences of `confidence` in `*.py`. |
| 9 | Not a static dashboard - conversational | **DONE** | Chat UI, `POST /api/ask/`. |
| 10 | Parameter-driven, repeatable business logic | **PARTIAL** | Tool args are parameterised (`n`, `threshold_pct`, `top_n`, `entity_type`); but health weights, slope threshold and recency window are hardcoded. |
| 11 | Start on NVIDIA free LLM APIs, OpenAI later | **DONE** | Dual provider, token-selected (`views.py:23-26`). |
| 12 | 15-day to 1-month validation sample | **DONE** | Data spans 01-Apr-2026 to 06-May-2026 (36 days). |
| 13 | Payment behaviour analysis | **STUB** | `get_payment_behavior` returns `DATA_NOT_AVAILABLE`. |
| 14 | Sales returns analysis | **STUB** | `get_return_analysis` returns `DATA_NOT_AVAILABLE`. |

**Reading:** the repo delivers a credible conversational shell and partial
implementations of **2 of the 5 required analytical modules** (Modules 1 and
5), built on **2 of the 8 inputs the requirement names** - Sales Orders and
Sales Invoices. Delivery information, payment behaviour, debit/credit notes
and sales returns are absent; the two tools that would need the last two are
stubs, and the other two have no tool at all.

---

## 3. System Architecture (as implemented)

### 3.1 Component map `[IMPLEMENTED]`

```mermaid
flowchart TB
    subgraph CLIENT["Browser - index.html (917 lines)"]
        UI["Chat UI<br/>vanilla JS, no framework"]
        AUTH["Auth modal<br/>token held in JS variable"]
        MD["markdownToHtml()<br/>line 837"]
    end

    subgraph VERCEL["Vercel - @vercel/python WSGI"]
        APP["app.py<br/>WSGI entry"]
        subgraph DJANGO["Django 5.2.7 + DRF"]
            IDX["_index_view<br/>urls.py:25"] -->|"serves"| UI
            API["/api/ask/  AgentQueryView<br/>views.py:41"]
            REL["/api/reload-data/  DataReloadView<br/>views.py:85"]
            SES["/api/session/id/  SessionClearView<br/>views.py:108"]
            HLTH["/api/health/  HealthView<br/>views.py:123"]
        end
        subgraph AGENT["llm_api.agent"]
            RUN["run_agent()<br/>agent.py:231"]
            LOOP["6-iteration<br/>tool loop"]
            CLNT["_build_client()<br/>agent.py:210"]
        end
        subgraph TOOLS["llm_api.analytics_tools"]
            REG["TOOL_REGISTRY<br/>12 functions"]
            LD["load_data()<br/>cached + locked"]
        end
    end

    subgraph NVIDIA["NVIDIA NIM API"]
        NEM["nvidia/nemotron-3-ultra-550b-a55b"]
    end

    subgraph FILES["data/ - 4 Excel workbooks, 211 KB"]
        F1["Sales Order"]
        F2["Sales Order Details"]
        F3["Sales Invoice Details"]
        F4["Sales Invoice header<br/>NEVER LOADED"]
    end

    UI -->|"POST /api/ask/  Bearer token"| API
    API -->|"token selects provider"| RUN
    RUN --> LOOP
    LOOP --> CLNT --> NEM
    LOOP --> REG --> LD
    LD --> F1
    LD --> F2
    LD --> F3
    F4 -.->|"not in DATA_FILES"| LD
    LOOP -->|"JSON result"| CLNT
    NEM -->|"answer text"| API
    API --> MD --> UI
```

### 3.2 Request lifecycle `[IMPLEMENTED]`

One HTTP round trip. The full path from keystroke to rendered answer:

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant I as index.html
    participant V as AgentQueryView
    participant A as run_agent()
    participant L as LLM API
    participant T as TOOL_REGISTRY
    participant D as data/ (Excel)

    U->>I: types query, presses Enter
    I->>I: sendQuery() line 684, appendTyping()
    I->>V: POST /api/ask/ {query, session_id}<br/>Authorization: Bearer &lt;token&gt;
    V->>V: _check_auth() line 15 -&gt; provider
    V->>V: history = _sessions[session_id] line 58
    V->>A: run_agent(query, history, provider) line 61

    loop up to 6 iterations (agent.py:253)
        A->>L: chat.completions.create(tools=12, temperature=1)
        L-->>A: message with optional tool_calls
        alt tool_calls present
            A->>T: TOOL_REGISTRY[name](**args) line 287
            T->>D: load_data() (cache hit after 1st call)
            D-->>T: so, sod, inv DataFrames
            T-->>A: dict result
            A->>L: append role=tool message line 293
        else no tool_calls
            A-->>V: {answer, tools_used, error: null}
        end
    end

    V->>V: append user+assistant to _sessions, cap [-20:] line 69-75
    V-->>I: {answer, tools_used, session_id, error}
    I->>I: markdownToHtml() line 837, render tool badges line 778
    I-->>U: structured answer + tool badges
```

### 3.3 Deployment topology `[OBSERVED]`

```mermaid
flowchart LR
    subgraph GH["GitHub nachiiiket/erp-bot"]
        R["main branch<br/>16 commits"]
    end
    subgraph V["Vercel project"]
        B["build: @vercel/python<br/>src app.py"]
        RW["rewrite /(.*) -> /app.py"]
        ENVV["environment variables<br/>NVIDIA_API_KEY, tokens, ..."]
    end
    subgraph DISK["Serverless instance filesystem"]
        DD["data/ 4 x .xlsx<br/>read-only, bundled"]
    end

    R -->|"git push / auto deploy"| B
    B --> RW
    B --> ENVV
    RW --> DISK
    BROWSER["Browser"] -->|"HTTPS"| RW
```

`vercel.json` is 14 lines: one `builds` entry (`app.py` via
`@vercel/python`) and one catch-all `rewrites` to the same. Everything -
the HTML page and all four API routes - is served by a single Django WSGI
application.

### 3.4 Why this shape `[DESIGN]`

| Decision | Benefit | Cost |
| --- | --- | --- |
| Single WSGI entrypoint for static + API | One deploy target, no CORS needed in production, no CDN/static pipeline | Full HTML re-read from disk on every page load (`urls.py:26-28`), no cache headers |
| Model never computes; pandas does | Numbers are auditable and exact; model cannot hallucinate a total | Every question must be answerable by one of 12 tools; anything else fails |
| OpenAI SDK pointed at NVIDIA's OpenAI-compatible endpoint | Free provider today, swap to OpenAI by changing `base_url` + key | Provider-specific extras (`chat_template_kwargs`, `reasoning_budget`) smuggled via `extra_body` |
| Excel on local disk, not a database | Zero-ops, data is a client drop, reload is a POST | Re-reads all 4 workbooks on cold start; no incremental update; no query pushdown |
| In-memory session dict | 4 lines, no Redis dependency | Sessions die with the instance - see F-08 |
| Token doubles as provider selector | One header, no user table, no JWT | Anyone with the token gets the backend - see F-10 |

---

## 4. Repository Map and Entrypoints `[OBSERVED]`

```
erp-bot/
|-- .gitignore                     227 lines - see F-09 (.env guarded, data/ not)
|-- .python-version                3.12
|-- app.py                         15 lines - Vercel WSGI entry
|-- manage.py                      20 lines - os.chdir(llm_project/) then execute
|-- index.html                    917 lines - the entire frontend
|-- package-lock.json              86 bytes, no package.json  (vestigial)
|-- README.md                      60 lines - live URL + public trial token
|-- requirements.txt                8 lines - duplicate of llm_project/requirements.txt
|-- vercel.json                    14 lines - build + catch-all rewrite
|-- data/                          4 xlsx, 211,365 bytes, TRACKED IN GIT
|
|-- llm_project/
|   |-- .env                       623 bytes, NOT tracked (correct)
|   |-- .env.example               60 lines, tracked - contains real trial token
|   |-- .python-version            3.12
|   |-- db.sqlite3                 131,072 bytes, ignored, never used by app code
|   |-- manage.py                  20 lines
|   |-- requirements.txt           8 lines
|   |
|   |-- llm_project/               Django project package
|   |   |-- settings.py           198 lines
|   |   |-- urls.py                37 lines - includes _index_view
|   |   |-- wsgi.py / asgi.py      standard
|   |
|   |-- llm_api/                   Django app = the whole product
|       |-- agent.py              305 lines - system prompt, tool schema, loop
|       |-- analytics_tools.py    529 lines - 12 tools + registry
|       |-- data_loader.py         89 lines - Excel -> DataFrames, cache
|       |-- views.py              142 lines - auth, 4 API views, session store
|       |-- urls.py                 8 lines - 4 routes
|       |-- models.py               2 lines - EMPTY
|       |-- tests.py                stub
|       |-- README.md              80 lines - STALE (still says `anthropic`)
|       |-- data/                  4 xlsx - duplicate copy, gitignored
|       |-- migrations/            empty
```

**Two copies of the data exist on disk.** The tracked `data/` at the repo
root and an ignored duplicate under `llm_project/llm_api/data/`. Only the
former is read (`data_loader.py:9-15`: default is `ROOT_DIR/'data'`, the
legacy path is the fallback if the default does not exist).

### 4.1 Entrypoint resolution `[VERIFIED]`

| Entry | Used by | Behaviour |
| --- | --- | --- |
| `app.py` | Vercel | inserts `llm_project/` on `sys.path`, sets `DJANGO_SETTINGS_MODULE`, returns `get_wsgi_application()` |
| `manage.py` (root) | local dev | `os.chdir(llm_project/)` then executes the inner `manage.py` |
| `manage.py` (inner) | local dev | standard Django; README instructs `cd llm_project && python manage.py runserver` |

**Hazard:** because the README's local instructions change the working
directory to `llm_project/`, and `.env.example:24` sets
`SALES_DATA_DIR=data` (**relative**), data resolution becomes
CWD-dependent. Verified:

| CWD | `DATA_DIR` | File exists? |
| --- | --- | --- |
| repo root | `D:\hns_git\erp-bot\data` (absolute default, env unset) | **Yes** |
| `llm_project/` | `data` (relative, from `.env`) | **No** - `FileNotFoundError` on first query |
| repo root | `data` (relative, from `.env`) | Yes, by coincidence |

The default path (env unset) is absolute and safe. The *documented* env
override is relative and breaks. See F-12.

---

## 5. Data Layer `[IMPLEMENTED]`

### 5.1 Files on disk `[OBSERVED]`

| # | Workbook | Rows read | Role |
| --- | --- | --- | --- |
| 1 | `Sales Order - ..._Date Wise Sales Order.xlsx` | 37 (after footer drop) | Order headers |
| 2 | `Sales Order Details - ..._Date Wise Sales Order.xlsx` | 415 | Order lines |
| 3 | `Sales Invoice Details - ..._Date Wise Sales Invoice.xlsx` | 3,333 | Invoice lines - **the primary fact table** |
| 4 | `Sales Invoice - ..._Date Wise Sales Invoice.xlsx` | 611 (610 docs) | Invoice headers - **never loaded** |

File 4's columns are
`Date, Customer Name, Amt.Total, Qty Total, Grand Total, Outstanding Amount, Due Date, Doc.No.`
- verified by reading it directly during preparation of this document.
`Outstanding Amount` and `Due Date` are exactly the fields that would make
payment behaviour, DSO, overdue buckets and realisation rate computable.

### 5.2 Loader: cache, lock, and the file map `[IMPLEMENTED]`

`data_loader.py` is 89 lines. The important parts:

| Lines | What |
| --- | --- |
| 9-15 | `ROOT_DIR = parents[2]` (repo root); `DATA_DIR` from `SALES_DATA_DIR` env, else `ROOT_DIR/'data'`, else legacy `llm_api/data` |
| 17-30 | `DATA_FILES` - exactly 3 entries, each overridable by an env var |
| 33-46 | `_resolve_data_file` accepts `http(s)://`, absolute, or `DATA_DIR / name`; `_read_data_file` dispatches `.csv` vs `.xlsx` |
| 49-56 | `_clean(df, date_col, required='Customer Name')` |
| 59-81 | `load_data()` - thread-locked memoised load |
| 84-89 | `reload_data()` - clears cache, re-loads (exposed as `POST /api/reload-data/`) |

Two details worth calling out:

- **Footer stripping is implicit, not explicit.** Query-report exports end
  with a `Grand Total` row whose `Customer Name` is blank. `_clean` drops
  rows with `dropna(subset=['Customer Name'])` (`:51`), and `load_data`
  does the same for the order header (`:69`). There is no date-pattern guard,
  so a footer with a populated customer name would leak in. It happens not
  to, because the footer row is empty in all four files.
- **The env var for the invoice file is named `SALES_INVOICE_DETAILS_FILE`
  and points at the *Details* workbook** (`:26-29`). There is no
  `SALES_INVOICE_FILE`. The naming makes it easy to believe the header is
  wired up when it is not.

### 5.3 Cleaning and derived columns `[IMPLEMENTED]`

```
_clean(df, date_col):
    dropna(subset = ['Customer Name'])                    # removes footer rows
    date_col = to_datetime(date_col, format='%d-%b-%y',
                           errors='coerce')               # 02-Apr-26 -> 2026-04-02
    week = date.dt.isocalendar().week                     # ISO week number
    month = date.dt.month
    half  = 'first'  if week <= 15 else 'second'          # hardcoded split point
```

Applied at `data_loader.py:74-75` to both `sod` and `inv`
(date column `Posting Date`). The order header is handled separately at
`:69-72` with date column `Date` and **no `month`, no `category`**.

Category derivation (`:77-78`), applied to `sod` and `inv` only:

```
category = Item Name.str.split('-').str[0].str.strip()
```

The item names are `~`-separated compound descriptors such as
`Boilersuit-~-MOL-~-StatSafe-Orange -JAP-BM.CL-CT-UV-~-~-2pc`, so the
first `-`-delimited token is the product family. This yields **46 categories**.

**Split-point fragility `[RISK]`:** `half` is defined as `week <= 15`, not as
the calendar midpoint. The data spans ISO weeks 14-19. A one-week shift in
the export window silently moves week 16 from "second" to "first" for no
reason other than the constant. The constant is not a parameter of any tool.

### 5.4 Verified dataset statistics `[VERIFIED]`

Produced by loading through the repository's own `load_data()`.

| Frame | Shape | Notes |
| --- | --- | --- |
| `so` | 37 x 10 | order headers, `Grand Total` 5,106,918.32 / `Amt.Total` 4,549,969.80 |
| `sod` | 415 x 13 | order lines, `Amount` 4,264,965.68, 32 distinct `Doc.No.` |
| `inv` | 3,333 x 13 | invoice lines, `Amount` 10,408,405.39, 610 distinct `Doc.No.` |

**Orphan-order cross-check.** `so` net minus `sod` net =
`4,549,969.80 - 4,264,965.68 = 285,004.12`. That is precisely the value of
the 5 order headers with zero detail lines - an independent confirmation of
the reference-integrity finding in the HNS analysis. The number is *not*
surfaced anywhere in erp-bot: no tool joins `so` to `sod`.

| Dimension | Value |
| --- | --- |
| Invoice weeks | 14, 15, 16, 18 (**week 17 absent, week 19 absent**) |
| Order weeks | 14, 15, 16, 18, 19 |
| `half` row split (invoice) | first 2,051 / second 1,282 |
| `half` row split (order) | first 27 / second 10 |
| Invoice customers | 33 |
| Invoice items | 182 raw / 182 after `str.strip()` |
| Categories | 46 |
| Rows with whitespace-padded `Item Name` | 133 rows, 5 distinct names (e.g. `' Woven Belt-~-Black'`, `'Boilersuit-~-ESM-R.Blue-~-BM.CL-PC-~-~-1pc '`) |

**Week 17 is missing from the invoice export entirely.** Because
`_trends()` builds its axis from `sorted(df['week'].unique())`
(`analytics_tools.py:250`), week 17 does not appear in any weekly series.
Weeks 16 and 18 are therefore plotted as *adjacent* points. The 8-day gap
(19-Apr to 26-Apr 2026, an empty ISO week) is invisible to every trend
computation in the codebase.

### 5.5 What the loader does not load `[GAP]`

```mermaid
flowchart LR
    subgraph ONDISK["data/ - all four tracked in git"]
        A1["Sales Order"]
        A2["Sales Order Details"]
        A3["Sales Invoice Details"]
        A4["Sales Invoice header<br/>Outstanding Amount<br/>Due Date"]
    end
    subgraph LOADED["DATA_FILES - data_loader.py:17-30"]
        B1["sales_orders"]
        B2["sales_order_details"]
        B3["sales_invoice<br/>(actually the Details file)"]
    end
    A1 --> B1
    A2 --> B2
    A3 --> B3
    A4 -.->|"0 lines of code"| X["NOTHING"]
```

Downstream consequences, all verified:

| Capability | Would need | Actual behaviour |
| --- | --- | --- |
| Outstanding / aged receivables | `Outstanding Amount` | Impossible - column never read |
| Due-date / overdue analysis | `Due Date` | Impossible - column never read |
| Payment terms distribution | `Payment Term` | Impossible - not even present in the header export |
| Realisation rate (cash vs gross) | header `Grand Total` vs line `Amount` | Impossible - `get_revenue_summary` compares line net to `so['Grand Total']`, which are different bases |
| `get_payment_behavior` | payment ledger | Returns `DATA_NOT_AVAILABLE` stub (`analytics_tools.py:483-495`) |
| Customer health with payment weight | outstanding + due date | Health score is 100% behavioural - see 6.2 |

---

## 6. Analytics Tool Catalogue `[IMPLEMENTED]` + `[VERIFIED]`

Twelve functions, registered in `TOOL_REGISTRY` (`analytics_tools.py:516-529`).
Ten compute; two are honest stubs. Every one is a pure function of the three
cached DataFrames - no network, no DB, no randomness.

### 6.0 Calling convention and shared helpers

| Helper | Lines | Behaviour |
| --- | --- | --- |
| `_slope_label(series, threshold=0.15)` | 7-21 | Trend classifier - the single most important function in the file, dissected in 6.5 |
| `_r(val)` | 24-25 | `round(float(val), 2)`, returns `0.0` for NaN |
| `load_data()` | via `:32` etc. | Every tool calls it; first call reads Excel, later calls hit the cache |

**Everything is named `orders` but counts invoices.** The aggregation
`orders=('Doc.No.', 'nunique')` appears at `:41`, `:81`, `:137`, `:163`,
`:343`. In `inv` (invoice lines), `Doc.No.` is the **invoice number**.
So:

| Where the model sees "orders" | What is actually counted |
| --- | --- |
| `get_top_n(metric='orders')` | distinct invoices |
| `get_customer_health_scores().orders` | distinct invoices |
| `get_discontinuation_candidates().orders` | distinct invoices |
| `get_revenue_summary().unique_orders` = 610 | distinct invoices (real sales orders = 37) |
| `get_revenue_summary().avg_order_value` = 17,062.96 | mean invoice value |

The system prompt tells the model to be precise with data
(`agent.py:35` "Do not invent data"), yet the tool layer hands it a field
that is systematically mislabelled by a factor of 16.5x (610 vs 37). This is
F-04 below.

---

### 6.1 `get_top_n(entity, n, metric='revenue')` - lines 30-66

**Schema** (`agent.py:39-53`): `entity` in `{customer, product}`, `n` integer,
`metric` in `{revenue, qty, orders}`.

```
group_col = 'Customer Name' if entity == 'customer' else 'Item Name'
total     = inv[agg_col].agg(agg_fn)              # global denominator
ranked    = inv.groupby(group_col)[agg_col].agg(agg_fn).desc().head(n)
share_pct = value / total * 100
```

Invalid `metric` silently falls back to `revenue` (`:43-44`) - no error is
returned to the model.

**Verified output, `get_top_n('customer', 5)`:**

| Rank | Customer | Revenue | Share |
| --- | --- | --- | --- |
| 1 | Best Marine Exports | 4,942,870.53 | 47.49% |
| 2 | Executive Ship Management Pte Ltd | 1,082,970.00 | 10.40% |
| 3 | Mas Workwear | 884,040.00 | 8.49% |
| 4 | Msc Shipmanagement Limited Cyprus | 568,635.00 | 5.46% |
| 5 | V.Ships India Pvt.Ltd. | 542,267.00 | 5.21% |

Total: 10,408,405.39. Top-5 concentration **77.06%** (top-5 revenue
8,020,782.53).

**Verified output, `get_top_n('product', 5)`:**

| Rank | Item | Revenue | Share |
| --- | --- | --- | --- |
| 1 | `Boilersuit-~-MOL-~-StatSafe-Orange -JAP-BM.CL-CT-UV-~-~-2pc` | 1,158,453.12 | 11.13% |
| 2 | `Boilersuit-~-MSC-~-StatSafe-Rust Yellow-...-CargoPkt-2pc` | 555,582.00 | 5.34% |
| 3 | `Parka-BM ColdStar-~-N.Blue-Polyster-...` | 501,192.00 | 4.82% |
| 4 | `Parka-BM Alpine-MOL-StatSafe-Flr.Green-...` | 342,619.20 | 3.29% |
| 5 | `Safety Shoes-Legasea-Xtreme-...-Steel Toe` | 341,720.24 | 3.28% |

**Caveat `[GAP]`:** the ranking is over raw `Item Name` strings, so
near-duplicate SKUs (differing only by a trailing space or a client code)
are ranked separately rather than as a product family. The 5 whitespace-padded
names found in 5.4 are treated as distinct products.

---

### 6.2 `get_customer_health_scores(customer_name=None)` - lines 71-118

**The formula** (`:94-100`, weights stated in the docstring `:74`):

```
score = rev_score + freq_score + div_score + rec_score
      = (revenue        / max_revenue)        * 40
      + (invoices       / max_invoices)        * 30
      + (unique_products / max_unique_products) * 20
      + max(0, 1 - days_since_last_invoice / 30) * 10
```

Bands (`:109`): `HIGH >= 60`, `MEDIUM >= 30`, else `LOW`.

Where `days_since = (latest_invoice_date_in_dataset - customer_last_invoice).days`
(`:97`) - **recency is measured against the newest invoice in the file, not
against today.**

**Properties `[DESIGN]`:**

| Property | Consequence |
| --- | --- |
| Min-max scaled against the *largest* customer | The top customer automatically earns 40/40 on revenue regardless of its actual health. Concentration and health become the same number. |
| No payment / outstanding term at all | A customer that never pays scores identically to one that pays in 3 days - the data is not loaded (5.5). |
| Recency measured against dataset max | With data spanning 28 days, `days_since` maxes at 28, so `rec_score` never drops below `max(0, 1-28/30)*10 = 0.67`. The 10-point recency term is effectively a constant across this dataset. |
| `orders` counts invoices | Frequency rewards customers invoiced many times for small amounts (Executive: 140 invoices, 10.4% of revenue) over customers invoiced few times for large amounts (Best Marine Exports: 20 invoices, 47.5%). |
| No denominator guard | If `max_rev` or `max_ord` were 0 the score would raise `ZeroDivisionError`, caught only by the agent's `except` at `agent.py:288-290`. |

**Verified output - all 33 customers, rating distribution:**

| Rating | Count | Score range |
| --- | --- | --- |
| HIGH | 1 | 69.29 |
| MEDIUM | 3 | 38.21 - 53.30 |
| LOW | 29 | 2.74 - 27.91 |

| Customer | Score | Invoices | Products | Days since | Rating |
| --- | --- | --- | --- | --- | --- |
| Best Marine Exports | 69.29 | 20 | 65 | 15 | HIGH |
| Executive Ship Management Pte Ltd | 53.30 | 140 | 31 | 15 | MEDIUM |
| Msc Shipmanagement Limited Cyprus | 39.08 | 97 | 12 | 0 | MEDIUM |
| V.Ships India Pvt.Ltd. | 38.21 | 104 | 18 | 12 | MEDIUM |
| Cash Sale | 27.91 | 75 | 20 | 16 | LOW |
| Best Marine Pvt Ltd Delhi | 16.59 | 7 | - | - | LOW |
| ... | ... | ... | ... | ... | LOW |
| Hydra Safety Trading Llc | 2.74 | 1 | - | - | LOW |

**Observations `[VERIFIED]`:**

- 29 of 33 customers are `LOW`. The threshold structure produces a
  near-uniform LOW classification, which makes the score useless as a
  triage device - the system prompt even works around it
  (`agent.py:30`: *"only flag customers with LOW or MEDIUM scores"*).
- `Cash Sale` - a ledger bucket, not a customer - ranks 5th with score 27.91
  from 75 invoices. It is a real row in the source data, and nothing in the
  pipeline excludes it. Recommending an account manager for "Cash Sale"
  is the visible failure mode of this.
- `Best Marine Exports` scores highest *and* is the concentration risk
  (47.49% of revenue). The score cannot express that.

---

### 6.3 `get_discontinuation_candidates(entity_type='both')` - lines 123-187

**Rules:**

```
latest_week = inv['week'].max()                       # = 18

PRODUCT  flagged  iff  revenue <= quantile(product_revenue, 0.10)
                   AND invoices <= 2
                   AND last_active_week < latest_week      # :145

CUSTOMER flagged  iff  invoices == 1
                   AND revenue < median(customer_revenue) / 2
                   AND last_active_week < latest_week      # :170
```

Each candidate carries a generated `reason` string (`:152-156`, `:176-180`)
that interpolates the actual figures - this is what satisfies the
requirement for "justifications".

**Verified output:** 13 products, 6 customers.

Products flagged (revenue / invoices / last active week):

| Product | Revenue | Invoices | Last week |
| --- | --- | --- | --- |
| `' Woven Belt-~-Black'` | 270.00 | 1 | 15 |
| `Bags-Carry-Dynacom-N.Blue-L22xB10xH12` | 440.00 | 2 | 15 |
| `Bags-Carry-Suntech-N.Blue-L22xB10xH12` | 492.00 | 1 | 16 |
| `Boilersuit-BM Accord-Seaspan-...-Orange` | - | - | - |
| `Boilersuit-BM Accord-WP-White-...` | - | - | - |
| `Boilersuit-BM Classic-SunTech-White-...` | - | - | - |
| `Boilersuit-~-ESM-R.Blue-...-1pc '` | - | - | - |
| `Boilersuit-~-Sima-...-N.Blue+Flr.Green-...` | - | - | - |
| `Boilersuit-~-Sima-...-White-...` | - | - | - |
| `Epaulet-~-Velcro-Propellor-~` | - | - | - |
| `Epaulet-~-Velcro-~-~` | - | - | - |
| `Peak Cap-Master` | - | - | - |
| `Shirt-BM Officer-Anglo-HS-...` | - | - | - |

(The first three are shown with figures from the tool's own output; the
remainder are listed by name from the same response.)

**Why the rule mostly works here `[VERIFIED]`:** `latest_week` is 18, and
week 18 contains almost no revenue (10,874.00 of 10,408,405.39 - 0.1%).
So "no activity after the last week" is effectively "no activity since
week 16", which is a much stronger statement than it reads. On a dataset
where the final week is busy, this rule would flag almost nothing.

**Two defects `[RISK]`:**

1. **Trailing/leading whitespace splits identity.** `' Woven Belt-~-Black'`
   (leading space) and `'Boilersuit-~-ESM-...-1pc '` (trailing space) are
   distinct group keys. If the same item also appears untrimmed, it is a
   separate product with separate revenue, and could pass the
   `<= 10th percentile` test only in its whitespace-inflated twin.
2. **Service lines with zero quantity are stock-adjacent.**
   `get_low_volume_analysis` (6.7) classifies `Delivery Courier Charges`
   as `DEAD_STOCK`. Discontinuation does not hit it (its revenue is high),
   but the two tools together would push the model toward "discontinue the
   courier line".

---

### 6.4 `get_volume_growth_alerts(entity_type='both', threshold_pct=20.0)` - lines 192-236

**Rule** (`:203-212`):

```
h1 = Amount where half == 'first'
h2 = Amount where half == 'second'
pct = 100.0                      if h1 == 0 and h2 > 0
    = (h2 - h1) / h1 * 100       otherwise
flag if pct >= threshold_pct
```

`half` comes from `week <= 15` (5.3). **A customer with `h1 = 0` is
assigned exactly `100.0%` growth**, not infinity - a bounded but arbitrary
value that is indistinguishable from a genuine +100% (`:207-208`).

**Verified output:** 12 growing customers, 40 growing products, threshold 20.

| Customer | First half | Second half | Growth |
| --- | --- | --- | --- |
| Goodwood Shipmanagement Pvt. | 3,445.82 | 14,934.15 | +333.40% |
| Ocs Services Dmcc (Valles) | 21,116.00 | 53,373.00 | +152.76% |
| Shane Marine Services Private Limited | 9,280.00 | 18,960.00 | +104.31% |

Top product: `Boilersuit-~-MOL No RR-...-2pc` at **+1,400.00%**.

**Asymmetry `[GAP]`:** the function name says "alerts" and the docstring
says "Flags entities growing > threshold". There is **no declining
counterpart** - the response keys are `growing_customers`,
`growing_products`, `threshold_pct`, `summary`. Declining entities are
simply not reported by this tool. The demo-mode canned answer
(`index.html:877-885`) correctly reflects this, but a user asking "who is
shrinking?" will get whatever `get_trend_direction` produces instead, which
uses a different method (6.5) and a different threshold.

---

### 6.5 `get_trend_direction(entity_type='both', entity_name=None)` - lines 241-284

The most consequential function in the codebase.

#### 6.5.1 The classifier `_slope_label` - lines 7-21

```python
def _slope_label(series, threshold=0.15):
    if len(series) < 2:      return 'INSUFFICIENT_DATA'
    x = np.arange(len(series))
    y = series.values.astype(float)
    if y.sum() == 0:         return 'NO_ACTIVITY'
    slope = np.polyfit(x, y, 1)[0]          # ordinary least squares
    pct_change = slope / (y.mean() + 1e-9)  # slope normalised by mean level
    if pct_change >  threshold: return 'GROWING'
    if pct_change < -threshold: return 'DECLINING'
    return 'STABLE'
```

In words: fit a straight line through the period series, express the
per-period slope as a percentage of the series mean, and compare against
+/-15%.

**Verified behaviour of the classifier in isolation:**

| Series input | Label | Comment |
| --- | --- | --- |
| `[10, 12, 14, 16]` | `GROWING` | clean upward trend, pct = +0.50 |
| `[10, 9, 11, 8]` | `STABLE` | noise around flat |
| `[5000, 0, 0, 0]` | `DECLINING` | immediate collapse |
| `[0, 0, 0, 0]` | `NO_ACTIVITY` | guard at `:13` |
| `[0, 0, 33028, 0]` | **`GROWING`** | **false positive - a single spike** |
| `[0, 0, 0, 5000]` | **`GROWING`** | single late spike also passes |

The single-spike case is not hypothetical: `Davic Ship Management` has
`weekly_revenue = {14: 0, 15: 0, 16: 33028, 18: 0}` and is returned in the
`growing` list with the recommendation *"Increasing trend - deepen
relationship, ensure stock availability, explore upsell."* Its entire
revenue is one invoice in one week; it never appears again. The slope is
positive purely because the mean is dragged down by the three zeros.

**Root cause `[DESIGN]`:** normalising a slope by `y.mean()` makes the
threshold scale-free, which is good, but it also means that **any series
whose mass is concentrated late** has a positive slope regardless of shape.
A symmetric series with mass concentrated *early* is symmetrically
`DECLINING`. The classifier has no notion of "how many periods of activity",
no minimum-activity guard, and no weighting for recency of the spike.

#### 6.5.2 What the tool returns - lines 249-284

```
all_weeks   = sorted(df['week'].unique())       # :250, from the FULL frame
weekly      = grp.groupby('week')['Amount'].sum().reindex(all_weeks, fill_value=0)
label       = _slope_label(weekly)
if label in ('GROWING', 'DECLINING'):  append to results      # :254
```

- Zero-filling over `all_weeks` is correct: gaps become explicit zeros.
- **`STABLE`, `NO_ACTIVITY` and `INSUFFICIENT_DATA` entities are dropped
  from the response entirely** (`:254`). The `summary` block reports only
  `growing_count` and `declining_count` (`:280-283`).

**Verified:** 33 customers + 182 products = 215 entities enter the
function; **39 return as `growing`, 124 as `declining`, and 52 are
silently discarded.** The response contains no `stable` key and no
`stable_count`, so a consumer cannot tell that 24% of the entity universe
went unreported.

This is not an accident - the docstring says so (`:244`: *"Returns only
GROWING and DECLINING - silent on STABLE/INSUFFICIENT"*), the tool
description says so (`agent.py:99`), and the system prompt makes it a rule
(`agent.py:29`: *"only report GROWING or DECLINING entities, skip STABLE"*).
It is a deliberate design choice whose consequence - that "is my customer
base stable?" is unanswerable - is never surfaced to the user.

- Customers and products are **merged into the same two lists** with no
  `type` field. The model must infer entity type from the name string.
- `declining` (124) outnumbers `growing` (39) by 3.2:1. Part of that is
  real (the period ends on a near-empty week 18), part is the classifier's
  asymmetry on sparse series.

**Verified sample of the `growing` list** (mixed customers and products):
`Davic Ship Management`, `Densay Marine Private Limited`,
`Eastaway (India) Private Limited`, `Goodwood Shipmanagement Pvt.`,
`Ocs Services Dmcc (Valles)`, `SM Services Fzc`, `Shane Marine Services
Private Limited`, `Synergy Maritime Recruitment Services Pvt Ltd`,
`Vigma Maritime Services Private Limited`, `Xt Ships Management India Pvt
Ltd`, then 29 products.

**Verified sample of the `declining` list:** `Apeejay Shipping Limited`,
`Arudra Engineers Private Limited`, `Bernhard Schulte Shipmanagement India
Private Limited`, `Best Marine Exports`, `Best Marine Online`,
`Best Marine Pvt Ltd Delhi`, `Cash Sale`, `Dynacom Tankers Management Pvt
Ltd`, `Mas Workwear`, `Scorpio Ship Management Sam`, ... then 112 products.

Note `Best Marine Exports` - 47.49% of all revenue - is labelled
`DECLINING`. It is, in this window (peak week 15, near-zero week 18), and
the system prompt will present that without the caveat that the series has
only four points, one of which is empty.

---

### 6.6 `get_order_to_invoice_analysis(customer_name=None)` - lines 289-329

**The algorithm:**

```python
so_rev  = sod.groupby('Customer Name')['Amount'].sum()   # :296  order lines
inv_rev = inv.groupby('Customer Name')['Amount'].sum()   # :299  invoice lines
merged  = pd.merge(so_rev, inv_rev, on='Customer Name', how='outer').fillna(0)
merged['gap']     = so_revenue - invoiced_revenue                     # :303
merged['gap_pct'] = (gap / (so_revenue + 1e-9)) * 100                 # :304
status = 'MATCHED'      if abs(gap_pct) < 5
       = 'UNDER_INVOICED' if gap > 0
       = 'OVER_INVOICED'                                             # :311
```

**Why it fails `[RISK]` - three independent problems:**

1. **There is no order-to-invoice key.** The join is on `Customer Name`
   only. Even if both sides were populated for the same customer, the tool
   would compare *aggregate* order value to *aggregate* invoice value, which
   is a period-overlap comparison, not a fulfilment comparison. The tool
   description promises *"Detects under-invoiced or unfulfilled orders"*
   (`agent.py:113`). It cannot: it cannot tell which invoice satisfies which
   order.

2. **Customer-name fragmentation makes the join mostly empty.** The order
   export has 12 customer strings; the invoice export has 33. An outer join
   therefore produces rows where one side is structurally zero:

   | Group | Count | Effect |
   | --- | --- | --- |
   | present on both sides | 7 | meaningful-ish |
   | order-only | 5 | `invoiced_revenue = 0` -> `UNDER_INVOICED`, gap_pct = 100 |
   | invoice-only | 26 | `so_revenue = 0` -> `OVER_INVOICED`, gap_pct = absurd |

   **26 of 38 rows (68%) are invoice-only customers that never had an
   order row at all.**

3. **Division by `1e-9` produces machine-scale numbers.** For
   `so_revenue = 0`:
   `gap_pct = (0 - 4,942,870.53) / (0 + 1e-9) * 100 = -4.94287053e+17`.

**Verified output (all 38 rows):**

| Status | Count |
| --- | --- |
| `OVER_INVOICED` | 30 |
| `UNDER_INVOICED` | 7 |
| `MATCHED` | **1** |
| max abs(gap_pct) | **4.94287053e+17** |

Worst offenders, all with `so_revenue = 0.0`:

| Customer | so_revenue | invoiced_revenue |
| --- | --- | --- |
| Best Marine Exports | 0.00 | 4,942,870.53 |
| Mas Workwear | 0.00 | 884,040.00 |
| Best Marine Pvt Ltd Delhi | 0.00 | 451,318.75 |
| Cash Sale | 0.00 | 126,295.73 |
| Elegant Marine Services Private Limited | 0.00 | 124,186.00 |
| International Maritime Institute | 0.00 | 122,388.00 |
| ... (20 more) | 0.00 | ... |

The `note` field then reads *"Invoiced Rs 4942870.53 more than ordered -
check for manual invoices."* - advice that would send a reader hunting for
a phantom manual invoice, when the truth is that the order export simply
does not contain this customer.

**Also inconsistent:** `total_so_revenue` returned by this tool is
`4,264,965.68` (order *detail* net), while `get_revenue_summary` reports
`total_so_value = 5,106,918.32` (order *header* gross). Two tools, two
different meanings for "SO value", in the same conversation.

---

### 6.7 `get_low_volume_analysis(top_n=20)` - lines 334-361

Not a filter - a **sort**. Take the bottom `top_n` products by summed `Qty`,
then stamp a verdict (`:355-358`):

```
DEAD_STOCK  if qty == 0
VERY_LOW    if qty <= 5
LOW         otherwise
```

**Verified output:** 20 rows - 2 `DEAD_STOCK`, 18 `VERY_LOW`.

| Product | Qty | Revenue | Invoices | Customers | Verdict |
| --- | --- | --- | --- | --- | --- |
| Delivery Courier Charges | 0 | 60,970.00 | 43 | 9 | **DEAD_STOCK** |
| Packing & Forwarding Charges | 0 | 138,910.00 | 3 | 1 | **DEAD_STOCK** |
| Blazer-Refer Coat-Black-PC-Double Breasted-2Off- ~~-BM-~ | 1 | 3,298.00 | 1 | 1 | VERY_LOW |
| `' Woven Belt-~-Black'` | 1 | 270.00 | 1 | 1 | VERY_LOW |
| Boilersuit-BM Accord-WP-White-...-2pc | 1 | 1,190.00 | 1 | 1 | VERY_LOW |

**Misclassification `[RISK]`:** the two `DEAD_STOCK` rows are **service
charges**, not inventory. They have no quantity by nature. `Delivery Courier
Charges` earned 60,970 across 43 invoices from 9 customers - labelling that
"dead stock" is plainly wrong, and the verdict is generated without any
inspection of the revenue, invoice count or item type. A model narrating
this tool would report two dead-stock SKUs that are in fact a profitable
ancillary service.

**Also:** `Qty` sums across mixed units of measure (`Nos` and `Pair`), so
`qty <= 5` is not a comparable threshold across products.

---

### 6.8 `get_revenue_summary()` - lines 366-388

The designated "starting point for general questions"
(`agent.py:136`).

**Verified output:**

```json
{
  "period": "01-Apr-2026 to 30-Apr-2026",
  "total_invoiced_revenue": 10408405.39,
  "total_so_value": 5106918.32,
  "total_invoice_line_items": 3333,
  "unique_customers": 33,
  "unique_products": 182,
  "unique_orders": 610,
  "weekly_revenue": {
    "week_14": 972988.28,
    "week_15": 6988992.75,
    "week_16": 2435550.36,
    "week_18": 10874.00
  },
  "top_categories": [ ...8 entries... ],
  "avg_order_value": 17062.96,
  "peak_week": 15
}
```

Top 8 categories:

| Category | Revenue | Share |
| --- | --- | --- |
| Boilersuit | 4,560,915.38 | 43.82% |
| Parka | 1,412,292.60 | 13.57% |
| Safety Shoes | 877,707.07 | 8.43% |
| Parka Pant | 511,166.40 | 4.91% |
| Safety Boots | 450,525.69 | 4.33% |
| Gloves | 379,029.66 | 3.64% |
| Winter Boilersuit | 325,004.00 | 3.12% |
| Uniform Pant | 201,863.90 | 1.94% |

**Four defects `[RISK]`, all in one 20-line function:**

1. **`period` is a hardcoded literal** (`:374`):
   `'01-Apr-2026 to 30-Apr-2026'`. The real invoice range is 02-Apr to
   30-Apr, and the order data extends to 06-May-2026. The field will never
   change, even after a data reload.
2. **Mixed measurement bases.** `total_invoiced_revenue` is line-level
   **net**; `total_so_value` is header-level **gross**
   (`so['Grand Total']`, `:376`). Putting them in the same object invites
   the model to compute a conversion rate between them. The correct
   order-side net figure (4,549,969.80) is never returned by any tool.
3. **`unique_orders` is 610** (`:380`) - that is invoices. Actual sales
   orders number 37.
4. **`week_17` does not exist** in `weekly_revenue`, and `week_18`
   (10,874.00 - 0.1% of revenue) is presented as a peer of `week_15`
   (6,988,992.75). A model asked "is revenue declining?" will see 4 points
   ending at 0.16% of the peak and say yes, with no signal that the final
   point is a partial/empty week.

`peak_week: 15` and `avg_order_value: 17062.96` are both correct.

---

### 6.9 `get_customer_deep_dive(customer_name)` - lines 393-434

Substring match (`str.contains(..., case=False)`, `:397-398`) against both
`inv` and `sod`. Returns revenue, invoices, qty, unique products,
`so_value`, trend, weekly series, top 5 products, and an `action` string.

**Verified output for `'V.Ships'`:**

```json
{
  "customer": "V.Ships",
  "total_revenue": 542267.00,
  "total_orders": 104,
  "total_qty": 792,
  "unique_products": 18,
  "so_value": 79752.00,
  "trend": "DECLINING",
  "weekly_revenue": {"week_15": 306902.00, "week_16": 235365.00},
  "action": "Declining activity - investigate satisfaction, pending orders, or competitive loss."
}
```

**Two defects, both verified:**

1. **It contradicts `get_trend_direction` (F-03).** This function computes
   `weekly = c_inv.groupby('week')['Amount'].sum()` (`:403`) with **no
   reindex to the full week axis**, then passes the 2-element sparse series
   `[306902, 235365]` to `_slope_label` -> `-26.4%` -> `DECLINING`.
   `get_trend_direction` zero-fills to `[0, 306902, 235365, 0]` and
   computes `-5.3%` -> `STABLE`, then **drops the row**. Verified:

   | Source | Result for V.Ships India Pvt.Ltd. |
   | --- | --- |
   | `get_trend_direction(entity_type='customer')` | **absent** from both lists |
   | `get_customer_deep_dive('V.Ships')` | **`trend: DECLINING`** + investigate action |

   The model, following `agent.py:29` (use `get_trend_direction` for trend
   questions), would report V.Ships as not-trending; following the deep-dive
   path, as declining. Both are "the tool's answer".

   The general form: **omitting zero-fill concatenates non-adjacent weeks as
   if adjacent.** An entity active only in weeks 14 and 18 produces a
   2-point series that looks like one period of change.

2. **Two customer universes are mixed.** `total_revenue` comes from the
   invoice side (33 customers), `so_value` from the order side (12
   customers, different spellings). `so_value: 79752.00` for V.Ships is
   whatever the order-detail export happens to call "V.Ships" - it is not
   the same population as the 542,267.00 on the invoice side, and the tool
   returns both under one customer heading with no reconciliation.

---

### 6.10 `get_product_deep_dive(product_name)` - lines 439-478

Substring match on `Item Name` (`:443`), then revenue, qty, unique
customers, `avg_rate = p_inv['Rate'].mean()` (`:462`), trend, weekly series,
top 5 customers, `action`.

**Verified output for `'Boilersuit'`:**

```json
{
  "product": "Boilersuit",
  "total_revenue": 4885919.38,
  "total_qty": 4060,
  "unique_customers": 30,
  "avg_rate": 1141.18,
  "trend": "DECLINING",
  "weekly_revenue": {"week_14": 473439.50, "week_15": 3323829.64,
                     "week_16": 1082089.24, "week_18": 6561.00},
  "action": "Declining product - check if customer-specific or market-wide. ..."
}
```

**Same label, two different scopes `[VERIFIED]` - a clean demonstration of
the substring-vs-category mismatch:**

| Source of the word "Boilersuit" | Method | Revenue |
| --- | --- | --- |
| `get_revenue_summary().top_categories` | derived `category` = first `-` token | **4,560,915.38** |
| `get_product_deep_dive('Boilersuit')` | `Item Name.str.contains('Boilersuit')` | **4,885,919.38** |
| Difference | `Winter Boilersuit` category | **325,004.00** |

`4,560,915.38 + 325,004.00 = 4,885,919.38` exactly. The deep dive silently
merges two product families because "Winter Boilersuit" *contains* the
substring "Boilersuit". A user who first asks for a revenue summary and
then asks for a Boilersuit deep dive receives two irreconcilable totals for
the same word, with no explanation in either response.

**Also:** `avg_rate` is an unweighted mean of line-level `Rate` across a
mixed-unit quantity column (Nos and Pair) - it is not a price, and it is
not comparable between products.

---

### 6.11 `get_payment_behavior(...)` - lines 483-495 `[BLOCKED]`

```json
{
  "status": "DATA_NOT_AVAILABLE",
  "message": "Payment behavior analysis requires Payment Entries data. Please upload
              the payment ledger Excel from your ERP. Once available, this tool will
              show: avg payment delay days, number of part-payments per invoice,
              outstanding amounts, and customers with chronic late payment behavior.",
  "required_columns": ["Customer", "Invoice Ref", "Payment Date", "Amount Paid", "Invoice Date"]
}
```

**Honest and well-formed** - it names the columns it needs and the insights
it would produce. It is the right pattern for a missing-data boundary.

**But the stated requirement is only half true `[GAP]`:**
"outstanding amounts" would not need a payment ledger at all - it needs
`Outstanding Amount` from the **Sales Invoice header workbook, which is
already in `data/` and already loaded by zero lines of code** (5.5). Aged
receivables and overdue buckets are likewise computable today from
`Outstanding Amount` + `Due Date`. Only "payment delay days" and
"part-payments" genuinely require a new export.

---

### 6.12 `get_return_analysis(...)` - lines 500-511 `[BLOCKED]`

Same pattern, `required_columns: ["Customer", "Item", "Return Date",
"Qty Returned", "Reason"]`. **Genuinely blocked:** no returns or credit-note
data exists anywhere in the repository. The only occurrence of the phrase
"Credit Note" in the entire Python tree is this stub's own message text
(`analytics_tools.py:506`).

---

### 6.13 Tool summary matrix `[VERIFIED]`

| # | Tool | Lines | Reads | Real output | Known defects |
| --- | --- | --- | --- | --- | --- |
| 1 | `get_top_n` | 30-66 | inv | Yes, exact | raw-string grouping; bad metric silently coerced |
| 2 | `get_customer_health_scores` | 71-118 | inv | Yes, 33 rows | no payment term; `orders` = invoices; self-normalising; 29/33 LOW |
| 3 | `get_discontinuation_candidates` | 123-187 | inv | Yes, 13+6 | whitespace identity; `latest_week` rule |
| 4 | `get_volume_growth_alerts` | 192-236 | inv | Yes, 12+40 | growth-only; `h1=0 -> 100%` |
| 5 | `get_trend_direction` | 241-284 | inv | Yes, 39+124 | drops 52 entities; spike false positive; merged types |
| 6 | `get_order_to_invoice_analysis` | 289-329 | sod+inv | Yes, **31/38 one-sided** | no join key; `/1e-9` overflow; mixed bases |
| 7 | `get_low_volume_analysis` | 334-361 | inv | Yes, 20 rows | services labelled DEAD_STOCK; mixed UoM |
| 8 | `get_revenue_summary` | 366-388 | so+inv | Yes | hardcoded period; gross vs net; `unique_orders` = invoices |
| 9 | `get_customer_deep_dive` | 393-434 | sod+inv | Yes | no zero-fill; contradicts #5; mixed universes |
| 10 | `get_product_deep_dive` | 439-478 | inv | Yes | substring scope; unweighted `avg_rate` |
| 11 | `get_payment_behavior` | 483-495 | - | Stub | claims data unavailable that is on disk |
| 12 | `get_return_analysis` | 500-511 | - | Stub | genuinely blocked |

---

## 7. Agent Loop `[IMPLEMENTED]`

### 7.1 The system prompt contract - lines 20-35

The entire behavioural specification is 16 lines of text:

```
You are an expert Sales Analytics AI for Best Marine Private Limited,
a marine safety equipment company. You analyze ERP sales data and provide
actionable business intelligence.

Data available: Sales Orders, Sales Order Details, Sales Invoices (Apr-May 2026).

Rules:
- Always call the relevant tool(s) before answering - never guess from memory.
- If a question involves top-N, extract the exact number N from the query.
- For trend questions, use get_trend_direction - only report GROWING or
  DECLINING entities, skip STABLE.
- For health questions, only flag customers with LOW or MEDIUM scores unless
  specifically asked.
- For discontinuation: always provide the 'reason' field in your explanation.
- For missing data (payments, returns): clearly state what data is needed.
- Structure answers with: Summary -> Key Findings -> Recommendations.
- Use ₹ for currency. Be direct and business-focused.
- Do not invent data. Only use what the tools return.
```

**Reading `[DESIGN]`:** three of these rules are workarounds for tool
defects rather than business requirements:

| Rule | What it is actually papering over |
| --- | --- |
| *"only report GROWING or DECLINING ... skip STABLE"* | The tool drops STABLE rows (6.5.2); the prompt prevents the model from saying "and 52 others were not reported" |
| *"only flag customers with LOW or MEDIUM"* | 29 of 33 are LOW (6.2); flagging all of them would be useless, so the prompt narrows a threshold the code cannot |
| *"Do not invent data"* | The `orders` field is mislabelled (6.0) and `period` is a hardcoded literal (6.8) - the prompt cannot fix either |

The prompt also hardcodes the client name and the date range
*"Apr-May 2026"*, so a data reload covering a different period leaves the
model describing the wrong window while `get_revenue_summary` simultaneously
reports a third window (`01-Apr-2026 to 30-Apr-2026`).

### 7.2 Tool schema - lines 37-182

`TOOL_DEFINITIONS` is a list of 12 OpenAI-style function specs
(`name`, `description`, `input_schema`), converted to the wire format by
`_openai_tools()` (`:185-196`). Descriptions are prose aimed at the model,
and they are **not always accurate**:

| Tool | Schema description | Reality |
| --- | --- | --- |
| `get_order_to_invoice_analysis` | *"Detects under-invoiced or unfulfilled orders"* | Cannot detect either - no join key (6.6) |
| `get_trend_direction` | *"Returns only GROWING and DECLINING (STABLE is silent)"* | Accurate, and explicitly documents the gap |
| `get_low_volume_analysis` | *"Identifies slow-moving or dead stock"* | Includes service lines with no quantity (6.7) |
| `get_top_n` | *"N can be any number"* | No `maximum` in the schema; `n=100000` is accepted |

Only three tools have a `required` field (`get_top_n`, `get_customer_deep_dive`,
`get_product_deep_dive`). The rest accept an empty object, which is correct
for the zero-argument tools but means a malformed call to
`get_trend_direction` silently runs with `entity_type='both'`.

### 7.3 Iteration protocol - lines 231-305

```mermaid
sequenceDiagram
    autonumber
    participant C as run_agent
    participant L as LLM API
    participant R as TOOL_REGISTRY

    C->>C: messages = [system] + history + [user] (234-236)
    C->>C: tools_used=[], raw_results={}, i=0
    loop i &lt; MAX_ITERATIONS = 6 (253)
        C->>L: model, messages, tools, tool_choice=auto,<br/>max_tokens=16384, temperature=1, top_p=0.95
        L-->>C: message
        alt message.tool_calls is empty
            C-->>C: return {answer, tools_used, error:null} (259-265)
        else tool_calls present
            C->>C: append assistant msg with tool_calls (267-271)
            loop each tool_call (273)
                alt name in TOOL_REGISTRY
                    C->>R: TOOL_REGISTRY[name](**args) (287)
                    R-->>C: dict
                else unknown name
                    C->>C: result = {error: "Unknown tool: ..."} (284)
                end
                alt tool raised
                    C->>C: log + result = {error: str(e)} (288-290)
                end
                C->>C: raw_results[name]=result;<br/>append role=tool msg (292-298)
            end
            C->>L: (next iteration)
        end
    end
    C-->>C: return {answer:"Agent reached max iterations...",<br/>error:"max_iterations_reached"} (300-305)
```

**Key properties `[IMPLEMENTED]`:**

| Property | Value | Line |
| --- | --- | --- |
| Iteration cap | 6 LLM calls | `:18`, `:253` |
| Parallel tool calls | Supported - all calls in a message are executed before the next LLM call | `:273-298` |
| Unknown tool | `{'error': ...}` returned to the model, loop continues | `:283-284` |
| Tool exception | Caught, logged with traceback, `{'error': str(e)}` returned to the model | `:288-290` |
| Non-JSON tool arguments | `json.JSONDecodeError` -> `tool_input = {}` | `:277-278` |
| Tool result caching | `raw_results` dict keyed by tool name - **later calls to the same tool overwrite earlier ones** | `:292` |
| `tools_used` | A flat list with duplicates preserved (calling `get_top_n` twice yields it twice) | `:280` |
| Return value | `{answer, tools_used, raw_tool_results, error}` - but `views.py` only forwards `answer`, `tools_used`, `session_id`, `error` | `:259-265` vs `views.py:77-82` |

**Design choice `[DESIGN]`:** error containment is excellent. A throwing tool
never fails the request; the model receives `{"error": "..."}` and can retry
with different arguments or explain the problem. This is a real strength.

**But `raw_tool_results` is computed and then discarded.** The response
object never carries it to the client (`views.py:77-82`), so the user sees
the model's prose and a list of tool *names*, never the underlying numbers.
For an auditability-driven project this is the wrong default: the JSON that
proves the answer is collected, and then thrown away.

### 7.4 Provider clients - lines 210-228

```python
# OpenAI path (:211-217)
OpenAI(api_key=OPENAI_API_KEY,
       http_client=httpx.Client(trust_env=False, timeout=120.0))

# NVIDIA path (:218-228)
OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL,
       http_client=httpx.Client(trust_env=False, timeout=120.0))
# + extra_body = {"chat_template_kwargs": {"enable_thinking": True},
#                 "reasoning_budget": 16384}
```

- **Both providers use the OpenAI SDK**; NVIDIA is just a different
  `base_url`. That is what makes the requirement's "start on NVIDIA, move to
  OpenAI later" a one-line change.
- `trust_env=False` deliberately ignores `HTTP_PROXY`/`HTTPS_PROXY`
  environment variables. On a locked-down corporate network this would fail
  to connect rather than route through the proxy - a defensible choice for
  an outbound API key, but undocumented.
- `timeout=120.0` on the transport, but `run_agent` has **no overall
  deadline**. Worst case: 6 iterations x 120s = 12 minutes, well beyond any
  serverless function timeout.
- The NVIDIA-only `extra_body` (`enable_thinking`, `reasoning_budget=16384`)
  is passed to the OpenAI path too? **No** - `extra` is `{}` for OpenAI
  (`:217`) and only populated for NVIDIA (`:225-228`), guarded by
  `if extra:` at `:250-251`. Correct.

### 7.5 Generation parameters - lines 241-251 `[RISK]`

```python
max_tokens  = 16384
temperature = 1
top_p       = 0.95
tool_choice = 'auto'
```

`temperature=1` with `top_p=0.95` is a **high-variance** sampling setting.
The requirement document asks for *"consistency & repeatability"* of
analytical output. The deterministic half of the system (pandas) delivers
that; the narrative half does not - the same question with the same tool
results can produce materially different prose, different emphasis, and a
different choice of which 5 of 124 declining entities to mention.

Nothing in the repository pins a seed or sets `temperature` from an env var.

### 7.6 Failure modes `[IMPLEMENTED]`

| Condition | Returned to client | Line |
| --- | --- | --- |
| No `Authorization` header / bad token | HTTP 401 `{"error":"Unauthorized"}` | `views.py:19,28` |
| Empty `query` | HTTP 400 `{"error":"query is required"}` | `views.py:56` |
| Missing provider API key | HTTP 400 `{"error":"OpenAI API key is missing..."}` | `agent.py:213,220` -> `views.py:62-63` |
| Any other exception in `run_agent` | HTTP 500 `{"error": str(e)}` | `views.py:64-66` |
| 6 iterations without a final answer | HTTP 200 with `answer: "Agent reached max iterations..."`, `error: "max_iterations_reached"` | `agent.py:300-305` |
| Excel file missing | HTTP 500 with the pandas traceback text | `views.py:64-66` |
| A tool raises mid-loop | **HTTP 200** - model narrates the error object | `agent.py:288-290` |

Note the last row: a tool failure is *not* an HTTP error. The client sees a
successful response whose `error` field is `null` and whose prose may be an
apology. Whether that is correct depends on whether you treat tool failure
as a degraded answer or as a system fault.

---

## 8. API Layer and Authentication `[IMPLEMENTED]`

### 8.1 Endpoints - `llm_api/urls.py:1-8`

| Method | Path | View | Auth |
| --- | --- | --- | --- |
| POST | `/api/ask/` | `AgentQueryView` (`views.py:41`) | Bearer |
| POST | `/api/reload-data/` | `DataReloadView` (`views.py:85`) | Bearer |
| DELETE | `/api/session/<session_id>/` | `SessionClearView` (`views.py:108`) | Bearer |
| GET | `/api/health/` | `HealthView` (`views.py:123`) | Bearer |
| GET | `/` | `_index_view` (`llm_project/urls.py:25`) | none - serves `index.html` |
| GET | `/admin/` | Django admin | Django session - but no models exist |

**Every API route, including the health check, requires the bearer token.**
There is no unauthenticated liveness probe, so an external uptime monitor
cannot be pointed at `/api/health/` without embedding a secret.

### 8.2 Token selects the provider - lines 11-28

```python
OPENAI_AUTH_TOKEN = getattr(settings, 'OPENAI_AUTH_TOKEN', '')
NVIDIA_AUTH_TOKEN = getattr(settings, 'NVIDIA_AUTH_TOKEN', '')

def _check_auth(request):
    auth = request.headers.get('Authorization', '').strip()
    if not auth.lower().startswith('bearer '):
        return 401, None
    token = auth[7:]
    if OPENAI_AUTH_TOKEN and token == OPENAI_AUTH_TOKEN:
        return None, 'openai'
    if NVIDIA_AUTH_TOKEN and token == NVIDIA_AUTH_TOKEN:
        return None, 'nvidia'
    return 401, None
```

**Design `[DESIGN]`:** the bearer token is simultaneously the credential and
the provider selector. One header, two roles, no user table. Neat.

**Three properties worth stating plainly:**

1. **`if OPENAI_AUTH_TOKEN and ...` - an empty token is never a match.**
   If only `NVIDIA_AUTH_TOKEN` is set (the default from `.env.example`),
   the OpenAI branch is skipped entirely rather than accepting an empty
   header. Correct.
2. **Tokens are compared with `==`, not a constant-time function.**
   Irrelevant for a low-traffic demo, wrong for anything real.
3. **The token does not identify a user.** Every holder of the same token
   shares one provider and one backend. There is no per-user identity, no
   rate limit, and no audit trail of who asked what.

### 8.3 Session store - lines 30-31, 58, 69-75

```python
# in-memory session store - replace with Redis/DB for production
_sessions: dict[str, list] = {}
```

```python
history = _sessions.get(session_id, []) if session_id else []        # :58
...
_sessions[session_id].append({'role': 'user', 'content': query})      # :72
_sessions[session_id].append({'role': 'assistant', 'content': result['answer']})  # :73
_sessions[session_id] = _sessions[session_id][-20:]                   # :75
```

| Property | Reality |
| --- | --- |
| Backing store | Python dict on the function instance |
| Persistence | None - lost on cold start, redeploy, or scale-out |
| Cap | `[-20:]` = **20 messages = 10 user/assistant exchanges**. The comment on `:74` says *"20 turns"* - off by 2x |
| What is stored | Only `query` and `answer` text. **Tool calls and tool results are not persisted**, so turn 3 of a conversation has no memory of what turn 1's tools returned |
| Ownership | `session_id` is client-supplied and never validated or bound to a token |
| Expiry | None. Sessions accumulate for the life of the instance |
| Cleared by | `DELETE /api/session/<id>/` - callable by anyone holding the token, for any session id |

**On Vercel specifically `[RISK]`:** serverless instances are disposable and
concurrent. Two requests with the same `session_id` can land on different
instances with independent `_sessions` dicts, so multi-turn conversation
silently degrades into single-turn. The frontend generates
`'sess-' + Date.now()` (`index.html:668`), so within one browser session the
id is stable - but the *server* side of that id is not.

### 8.4 Dead code `[OBSERVED]`

`_get_provider_api_key(request)` at `views.py:34-38` is defined and never
called - one occurrence in the whole tree, its own definition. It implements
a *different* auth scheme (pass the provider API key straight through in the
`Authorization` or `X-Api-Key` header), which would have made the backend a
pass-through proxy for the caller's key. It is a fossil of an abandoned
approach.

---

## 9. Frontend `[IMPLEMENTED]`

`index.html` - 917 lines: CSS lines 8-499, markup 501-649, JavaScript 651-915.
No build step, no framework, no dependencies except two Google Fonts.

### 9.1 Layout

CSS grid, two columns and two rows (`:32-40`):

```
+--------------------------------------------------+
| header: logo, LIVE badge, session id              |
+------------+-------------------------------------+
| sidebar    | main                                |
| 11 quick   | chat area                           |
| queries    |                                     |
| 4 hardcoded| session bar + clear                 |
| stats      | textarea + send                     |
+------------+-------------------------------------+
```

Collapses to single-column below 640px, sidebar hidden (`:490-498`).

**The sidebar stats are hardcoded** (`:593-610`): `DATA PERIOD Apr-May '26`,
`CUSTOMERS 33`, `PRODUCTS 182`, `INVOICED Rs1.04Cr`. They match the current
data exactly - and will silently rot the moment `data/` is reloaded with a
different export. Nothing derives them from `/api/health/`.

### 9.2 Auth and session on the client - lines 652-681

```javascript
let AUTH_TOKEN = '';   // held in a JS variable, never persisted
let SESSION_ID = '';
let DEMO_MODE  = false;

function saveAuth() {
    AUTH_TOKEN = document.getElementById('auth-token-input').value.trim();
    SESSION_ID = 'sess-' + Date.now();
    ...
}
function useDemoMode() {
    DEMO_MODE = true;
    SESSION_ID = 'demo-' + Date.now();
    ...
}
```

- The token lives in a JS variable for the page's lifetime - no
  `localStorage`, no cookie. Refreshing the page requires re-entry. A
  deliberate, reasonable choice.
- `apiBase()` (`:658-661`) returns `http://localhost:8000/api` when the page
  is opened via `file://`, otherwise `${location.origin}/api`. This is what
  makes the file work both double-clicked and served by Django.

### 9.3 Rendering and XSS - lines 773-856

`appendAiMsg(text, tools)` sets `div.innerHTML = markdownToHtml(text) + badges`
(`:784`). `markdownToHtml` (`:837-852`) **escapes `&`, `<`, `>` as its first
operation**, then applies `**bold**`, `*italic*`, backticks, `#`->`<h3>`,
`-`->`<li>`, blank-line->`<p>`, newline->`<br/>`. Because escaping happens
first, model output cannot inject tags. User input goes through a separate
`escapeHtml` (`:854-856`) at `:767`.

**Assessment `[DESIGN]`:** this is a correct minimal defence for a
tool-augmented chat UI where the only untrusted string is model output.
The residual risks are cosmetic, not security:

| Issue | Effect |
| --- | --- |
| `/(<li>.*<\/li>)/s` is greedy (`:847`) | All `<li>` runs get wrapped in a single `<ul>` - one list for the whole message |
| No link autolinking | URLs render as plain text - a feature, arguably |
| `escapeHtml` does not escape quotes (`:855`) | Irrelevant here, since user text is placed in an element body, not an attribute |

### 9.4 Demo mode - lines 674-681, 858-914 `[RISK]`

When no token is offered, the user can choose *"Use demo mode"*. The client
then matches the query against five regexes (`:861-885`) and returns a
**hardcoded canned answer**, after a fake 1.4-2.2s delay (`:894`).

The canned figures were checked against live tool output during preparation
of this document:

| Canned claim (`index.html`) | Live tool output | Match |
| --- | --- | --- |
| Best Marine Exports Rs49,42,870 (47.5%) | 4,942,870.53 (47.49%) | yes |
| Total Invoiced Rs1,04,08,405 | 10,408,405.39 | yes |
| Total SO Value Rs51,06,918 | 5,106,918.32 | yes |
| Avg Order Value Rs17,063 | 17,062.96 | yes |
| Week 14 Rs9,72,988 / 15 Rs69,88,993 / 16 Rs24,35,550 / 18 Rs10,874 | 972,988.28 / 6,988,992.75 / 2,435,550.36 / 10,874.00 | yes |
| Boilersuit 43.8%, Parka 13.6%, Safety Shoes 8.4% | 43.82 / 13.57 / 8.43 | yes |
| 13 products flagged for discontinuation | 13 | yes |

**The demo answers are currently accurate.** The risk is structural: they
are literals in HTML with no link to `data/`, and there is no test or
generation step keeping them honest. The first data reload that changes a
number turns demo mode into a source of confidently wrong figures - and
demo mode is one click away from anyone who does not have a token.

---

## 10. Defect Register (ranked) `[RISK]`

| ID | Severity | Defect | Trigger | Evidence |
| --- | --- | --- | --- | --- |
| **F-01** | Critical | Order-to-invoice join on customer name + division by `1e-9` yields `gap_pct` up to 4.94e17; 31/38 rows have an empty join side, only 1 `MATCHED` | Ask any fulfilment question | `analytics_tools.py:296-311`, verified output 6.6 |
| **F-02** | High | Invoice header workbook (`Outstanding Amount`, `Due Date`) shipped, tracked, and never loaded; payment/DSO/overdue impossible | Any payment question | `data_loader.py:17-30` has 3 keys; 4 files in `data/` |
| **F-03** | High | Same entity gets contradictory trends: `get_trend_direction` omits V.Ships (STABLE), `get_customer_deep_dive` says DECLINING | Ask a trend question, then a deep dive | Verified in 6.9; `analytics_tools.py:403` vs `:252` |
| **F-04** | High | Field named `orders` counts *invoices* everywhere (610 vs 37); `unique_orders`, `avg_order_value`, health frequency all inherit it | Any "orders" question | `analytics_tools.py:41,81,137,163,343,380,386` |
| **F-05** | High | `get_trend_direction` silently drops 52 of 215 entities (24%) and reports no `stable` key | Any trend question | `analytics_tools.py:254,280-283`; verified 39+124 vs 215 |
| **F-06** | Medium | `_slope_label` labels a single mid-series spike as `GROWING` (e.g. `[0,0,33028,0]`) | Sparse customer/product | `analytics_tools.py:15-18`; verified 6.5.1 |
| **F-07** | Medium | `get_product_deep_dive('Boilersuit')` = 4,885,919.38 vs summary category 4,560,915.38 (substring merges Winter Boilersuit) | Summary then deep dive | Verified: difference = 325,004.00 exactly |
| **F-08** | Medium | In-memory `_sessions` dict; multi-turn breaks on Vercel cold start / scale-out; `[-20:]` is 10 turns not 20 | Second turn after a cold start | `views.py:31,75` |
| **F-09** | Medium | `.gitignore:218` guards `llm_project/llm_api/data/*.xlsx` but root `data/*.xlsx` is tracked; comment says "Private ERP/business data" | `git ls-files` | 4 workbooks tracked; `check-ignore` exit 1 |
| **F-10** | Medium | Trial bearer token `nv-token-2603` published in tracked `.env.example:20` and `README.md:45` | Anyone reading the repo | Both files |
| **F-11** | Medium | `get_revenue_summary.period` is the literal `'01-Apr-2026 to 30-Apr-2026'` | Any summary question | `analytics_tools.py:374` |
| **F-12** | Medium | `.env.example:24` sets relative `SALES_DATA_DIR=data`; combined with README's `cd llm_project` this breaks data loading | Local dev per README | Verified: `exists = False` from `llm_project/` |
| **F-13** | Medium | `get_low_volume_analysis` labels service lines (`Delivery Courier Charges`, Rs60,970 across 43 invoices) as `DEAD_STOCK` | Any stock question | `analytics_tools.py:356`; verified output |
| **F-14** | Low | `temperature=1`, `top_p=0.95` contradict the repeatability requirement | Every request | `agent.py:247-248` |
| **F-15** | Low | `get_revenue_summary` mixes order gross (5,106,918.32) with invoice net (10,408,405.39) in one object | Any summary question | `analytics_tools.py:375-376` |
| **F-16** | Low | Demo-mode canned answers are HTML literals with no link to `data/` | Data reload + demo user | `index.html:859-887` |
| **F-17** | Low | `SECRET_KEY` silently falls back to a well-known insecure value whenever `VERCEL` or `CI` is set | Deploy without `DJANGO_SECRET_KEY` | `settings.py:73-78` |
| **F-18** | Low | `session_id` is client-supplied, unvalidated, unbound to token; no ownership check on `DELETE /api/session/<id>/` | Crafted request | `views.py:53,114-120` |
| **F-19** | Low | `raw_tool_results` collected then discarded - no audit trail of the numbers behind an answer | Every request | `agent.py:239,292` vs `views.py:77-82` |
| **F-20** | Low | Whitespace-padded `Item Name` (133 rows, 5 names) split product identity | Grouping by item | Verified 5.4 |
| **F-21** | Low | `llm_api/README.md` still documents `pip install anthropic` and old filenames | Following in-app README | `llm_api/README.md` |

### 10.1 The three defects an interviewer will ask about

**F-01.** *Why is `gap_pct` 4.94e17?* Because the denominator is
`so_revenue + 1e-9` and 26 customers have `so_revenue == 0`. The `1e-9`
guards against `ZeroDivisionError` but converts a divide-by-zero into a
large finite number that looks like data. The correct fix is not a bigger
epsilon - it is to **not compute a percentage when the base is zero**, and
more fundamentally, to not attempt an order-to-invoice join on a field that
is not a key.

**F-03.** *Why do two tools disagree?* Because they feed the same classifier
differently-shaped input. `get_trend_direction` zero-fills over the global
week axis; `get_customer_deep_dive` passes the entity's own sparse week
groupby. A 2-element series and a 4-element zero-filled series over the same
underlying data produce different slopes. The classifier is fine; **the
preprocessing is not shared.** Extract one
`weekly_series(df, group_col, entity)` helper and both paths become
identical.

**F-02.** *Why is payment analysis blocked when the data is in the repo?*
Because `DATA_FILES` maps three filenames and the fourth workbook was never
added to the map. The env var that *sounds* like it loads invoices
(`SALES_INVOICE_DETAILS_FILE`) loads the *Details* file. Fixing it is a
five-line change - add an `invoice_headers` key, a loader branch, and join
on `Doc.No.` - which would unlock outstanding, due date, overdue buckets and
a payment weight for the health score simultaneously.

---

## 11. Security Review `[RISK]`

| # | Finding | Severity | Detail |
| --- | --- | --- | --- |
| S-1 | Private ERP data in a public repository | **High** | 4 workbooks (211,365 bytes) containing real customer names, item-level pricing and revenue totals are tracked in `https://github.com/nachiiiket/erp-bot.git`. `.gitignore:217-219` was written specifically to prevent this - its comment reads *"Private ERP/business data. Store/upload this intentionally, not by accident."* - but the pattern targets the legacy path `llm_project/llm_api/data/`, not the live `data/`. The guard is aimed at the wrong directory. |
| S-2 | Bearer token published | **Medium** | `.env.example:20` contains the real value `NVIDIA_AUTH_TOKEN=nv-token-2603` and `README.md:45` advertises it as *"Trial access"*. Anyone can drive the backend and consume the configured NVIDIA quota. This appears intentional for a demo, but it means the only thing between the public and `NVIDIA_API_KEY` is a string in a public file. |
| S-3 | Silent insecure `SECRET_KEY` fallback | **Medium** | `settings.py:74-78`: if `DJANGO_SECRET_KEY` is unset and `DEBUG`/`VERCEL`/`CI` is truthy, a hardcoded key is used instead of failing. On Vercel (`VERCEL` set) a misconfigured deploy therefore succeeds quietly with a publicly-known key. |
| S-4 | No rate limiting or identity | **Medium** | No throttling on `/api/ask/`, no per-user identity, no query log. The cost of a runaway loop (6 LLM calls per request at 16,384 max tokens) is unbounded per token holder. |
| S-5 | Session ids not bound to credentials | **Low** | `session_id` is arbitrary client input (`views.py:53`); history is read and written by whoever supplies the id (`:58,69-75`). A guessed/observed id lets a caller inject context into another party's conversation. |
| S-6 | Exception text returned to client | **Low** | `views.py:66` returns `str(e)` on HTTP 500 - filesystem paths and pandas internals can leak. |
| S-7 | Admin route exposed with default key | **Low** | `/admin/` is registered (`llm_project/urls.py:34`) though `llm_api` defines no models. Harmless but unnecessary attack surface. |
| S-8 | `.env` correctly excluded | **Good** | `.gitignore:151-153` ignores `.env` and `.env.*` with `!.env.example`. `git ls-files` confirms `llm_project/.env` (623 bytes) is **not** tracked. The one secret-handling control that works as intended. |

**Positive findings `[IMPLEMENTED]`:** `SECRET_KEY` is required in a true
production context; CORS defaults to off (`CORS_ALLOW_ALL_ORIGINS` defaults
to `DEBUG`, `settings.py:189`); the model output is HTML-escaped before
rendering (9.3); API keys never reach the browser (only auth tokens do);
`trust_env=False` prevents proxy-based interception of the outbound key.

---

## 12. Technology Choices and Trade-offs `[DESIGN]`

| Choice | Why it is right for this project | What it costs |
| --- | --- | --- |
| **Tool-calling agent, not RAG** | The corpus is structured tabular data, not text. SQL/pandas answers are exact; vector search over rows would be both slower and wrong. | Every question must be anticipated by one of 12 tools. Novel questions fail rather than approximate. |
| **Pandas in-process, not SQL** | 3,333 rows is ~200 KB in memory. A query planner is pure overhead; and Excel ingestion already lands you in pandas. | No pushdown, no indexes, no concurrency beyond the loader lock. Fine at this size, a wall at 100x. |
| **Excel as the store** | The client already exports it; zero migration, `reload_data()` is the update mechanism. | Full re-read on every cold start; no schema enforcement; footers stripped by an implicit `dropna`. |
| **OpenAI SDK pointed at NVIDIA** | Provider portability for free; the requirement explicitly plans an OpenAI migration. | Provider quirks hidden in `extra_body`; no NVIDIA-specific error handling. |
| **Bearer token as provider selector** | Avoids user accounts, JWT, OAuth - the whole auth stack the `.env.example` still advertises (`MONGO_`, `JWT_SECRET`, `FERNET`, `AWS_` - all with 0 code references). | No identity, no scoping, no rotation, no audit. |
| **Vanilla single-file frontend** | No build, no node_modules, no framework upgrade treadmill. 917 lines total, deploys as one asset. | All state in globals; the markdown renderer is hand-rolled; no virtualised scrollback. |
| **In-memory sessions** | Four lines and no infrastructure. | Broken on serverless - the exact platform chosen for deployment (F-08). |
| **Error-swallowing in the tool loop** | One bad tool call never fails a request; the model self-corrects. | Failures are invisible in the HTTP status; the client cannot distinguish "answered" from "degraded". |
| **`raw_tool_results` computed, not returned** | Keeps responses small; the model already saw the numbers. | No audit trail for an auditability-driven product (F-19). |

**The unresolved tension `[DESIGN]`:** the project's stated goal is
*repeatable, parameter-driven analysis with confidence levels*. It achieves
determinism on the arithmetic side and explicitly does not achieve it on the
narrative side (`temperature=1`), does not emit confidence at all, and hard
codes the parameters that should have been configurable (health weights,
slope threshold, half-split week, period literal). The architecture is right;
the parameterisation stopped one layer short.

---

## 13. Testing and Validation - what was actually run `[VERIFIED]`

### 13.1 What exists in the repository `[OBSERVED]`

| Artefact | State |
| --- | --- |
| `llm_api/tests.py` | Untouched Django stub - no tests |
| CI | None (no `.github/`) |
| Lint config | None (`.ruff_cache` ignored in `.gitignore:209` but no `ruff` config) |
| Type checking | None |

### 13.2 What was executed to produce this document

All of the following ran against the repository's own code with
`sys.path` pointing at `llm_project/`. The Django and OpenAI layers were
**not** exercised (`django`, `openai`, `httpx` are not installed in the
verification environment), so no end-to-end agent run was performed.

| Check | Method | Result |
| --- | --- | --- |
| Data loads | `load_data()` | `so` 37x10, `sod` 415x13, `inv` 3333x13 |
| Revenue reconciliation | sum `Amount` | 10,408,405.39 - matches `get_revenue_summary` |
| Orphan-order cross-check | `so.net - sod.net` | 285,004.12 - matches the independent HNS analysis |
| All 10 computing tools | direct invocation | all returned without exception |
| Both stubs | direct invocation | `DATA_NOT_AVAILABLE` with `required_columns` |
| `_slope_label` boundary cases | 6 hand-built series | see table 6.5.1, incl. 2 false positives |
| Trend entity accounting | 39 + 124 vs 33 + 182 | **52 entities dropped**, no `stable` key |
| F-03 contradiction | `get_trend_direction` vs `get_customer_deep_dive` on V.Ships | absent vs `DECLINING` |
| F-07 scope mismatch | summary category vs deep dive | difference = 325,004.00 = Winter Boilersuit exactly |
| F-01 magnitude | `max(abs(gap_pct))` | 4.94287053e+17; status counts 30/7/1 |
| Header workbook unread | `pd.read_excel` on file 4 | 611 rows, cols include `Outstanding Amount`, `Due Date` |
| Relative `SALES_DATA_DIR` | resolve from `llm_project/` CWD | `exists = False` (F-12) |
| Tracked-file inventory | `git ls-files` | 4 root workbooks tracked; `.env` not tracked; legacy `data/` ignored |
| Dead-code grep | `_get_provider_api_key`, `MONGO_`, `AWS_`, `EMAIL_`, `JWT_`, `FERNET`, `boto3`, `pymongo` | dead code = 1 (its own def); unused config families = 0 references |
| Requirement-concept grep | `confidence`, `region`, `bottleneck`, `potential` | 0 occurrences each in `*.py` |
| Demo-answer accuracy | canned figures vs live tool output | 7/7 exact (9.4) |
| SHA256 of data copies | root `data/` vs HNS copies | byte-identical (prior session) |
| Cold `load_data()` timing | `perf_counter` around first call | **1,631 ms**, then cached |
| Warm tool timing (20 runs each) | `perf_counter` per call | `get_top_n` 0.85 ms mean; `get_customer_health_scores` 8.73 ms mean; `get_trend_direction` 161.01 ms mean |
| Order-to-invoice join anatomy | outer merge + status counts | 38 rows = 26 `so==0` + 5 `inv==0` + 7 both; statuses 30/7/1 |

### 13.3 What could not be tested `[BLOCKED]`

| Item | Reason |
| --- | --- |
| End-to-end `POST /api/ask/` | `django`, `djangorestframework`, `openai`, `httpx` not installed |
| LLM responses, tool-selection quality | Requires `NVIDIA_API_KEY`; not available and must not be read from `.env` |
| Vercel deployment behaviour | No deploy access |
| Session loss on cold start | Requires a deployed serverless environment |
| `django check` / migrations | Django not installed |

---

## 14. Risks and Limitations

### 14.1 Limitations of this document `[BLOCKED]`

1. **No end-to-end run.** Every `[VERIFIED]` figure comes from importing
   `data_loader` and `analytics_tools` directly. The agent loop, the HTTP
   layer, the auth path and the frontend were verified by reading source,
   not by execution. Tool-*selection* quality (does the model pick
   `get_order_to_invoice_analysis` when it should?) is entirely untested.
2. **No LLM output sampled.** All statements about what the model will say
   are inferences from the system prompt and tool descriptions, not
   observations.
3. **One dataset, one window.** All behaviour was characterised on 36 days
   of data from a single company. The `half <= 15` split, the
   `latest_week` discontinuation rule and the recency term all behave
   differently on other windows - in several cases, drastically so.
4. **`.env` not read.** Its contents were deliberately not inspected.
   Whether `SALES_DATA_DIR` is actually set to the relative value shown in
   `.env.example` is therefore `[ASSUMPTION]`, not verified. The F-12 hazard
   is conditional on it.

### 14.2 Limitations of the system itself

| Domain | Not computable | Blocking reason |
| --- | --- | --- |
| Payments / DSO / overdue | Anything | Header workbook never loaded (F-02) |
| Sales returns | Anything | No data exists; tool is a stub |
| Order-to-cash fulfilment | Anything | No order-invoice key; customer-name join is structurally empty for 26/38 customers (F-01) |
| Regional analysis | Anything | No region field in any workbook |
| Delivery / bottleneck / delay | Anything | No delivery or PO data |
| Customer potential | Anything | No model, no input data |
| Confidence / certainty | Anything | No confidence field in any tool schema or response |
| Entity resolution | Anything | No canonical customer or item identity; 33 invoice names vs 12 order names, 133 whitespace-padded rows (F-20) |
| Trend stability | "Is my base stable?" | STABLE entities are dropped from the response (F-05) |
| Multi-turn reasoning over tools | Any | Session history stores only prose, not tool results (8.3) |
| Historical comparison | Anything | Single window; no prior period in the data |

### 14.3 Scalability ceiling `[DESIGN]`

| Dimension | Current | Behaviour if it grows |
| --- | --- | --- |
| Rows | 3,333 | Measured cached cost on this data: `get_top_n` **0.9 ms**, `get_customer_health_scores` **8.7 ms**, `get_trend_direction` **161 ms** (it rebuilds 215 weekly series). Cost scales roughly linearly with rows, so 10M rows would put the trend tool at minutes per call x up to 6 iterations. |
| Files | 4, one-time read | Measured cold `load_data()`: **1,631 ms** on first request, then cached. This is paid on every serverless cold start and grows linearly with file size; there is no incremental load. |
| Sessions | unbounded dict | Memory leak per instance; no TTL |
| Conversation depth | 10 exchanges | Truncated silently, oldest first, no user-visible signal |
| Tools | 12 | Every tool description is sent on **every** LLM call. At ~300 tokens of schema, 12 tools is ~3,600 tokens of prompt per iteration, x6 iterations. |
| Concurrent users | 1 token | Shared quota, shared provider, no isolation |

**Measured timings `[VERIFIED]`:** all three figures above were obtained by
running the repository's own functions 20 times against the cached DataFrames
on the verification machine. The 161 ms trend cost is the outlier and is
dominated by `groupby('week')` + `reindex` per entity - it is the reason
`get_trend_direction` is the tool most likely to approach a serverless
timeout once data grows.

---

## 15. Interview Questions and Model Answers

### Architecture

**Q1. Walk me through what happens when I ask "top 5 customers by revenue".**
The browser POSTs `{query, session_id}` with a bearer token to
`/api/ask/`. `AgentQueryView.post` validates the token via `_check_auth`,
which also selects the provider, and fetches any stored history. `run_agent`
assembles `[system] + history + [user]` and makes the first completion call
with 12 function schemas. The model returns a `get_top_n` tool call with
`{entity: "customer", n: 5}`. We look it up in `TOOL_REGISTRY`, call it, get
back five ranked dicts with revenue and share percentage, serialise them into
a `role: tool` message, and loop. The second call returns prose with no tool
calls, so we return `{answer, tools_used: ["get_top_n"]}`. The view appends
the user and assistant messages to `_sessions`, caps history at 20 messages,
and returns the JSON. The frontend escapes HTML, renders the markdown, and
appends a `get_top_n` badge. Total: two LLM calls, one pandas groupby, one
Excel read on the first request only.

**Q2. Why can the model not hallucinate a number?**
Because it never does arithmetic. Every figure in the answer comes from a
tool's JSON, and the prompt forbids anything else. The residual risk is not
hallucination of *values* but hallucination of *framing* - choosing the
wrong tool, or narrating a correct number without the caveat that makes it
safe (as with the hardcoded `period` field in `get_revenue_summary`).

**Q3. Where is the state?**
There is no database. `models.py` is empty and `db.sqlite3` is unused. All
analytical state is the three cached DataFrames; all conversational state is
a module-level dict. The only durable state is the Excel files themselves.

**Q4. What happens on a Vercel cold start?**
The instance boots, Django loads settings, which parses `.env` into
`os.environ`, then the first request triggers `load_data()` - four
`pd.read_excel` calls totalling ~211 KB, cached under a lock for the life of
the instance. Session history from previous instances is gone, so any
multi-turn conversation silently restarts.

### Data engineering

**Q5. How do you strip the footer rows out of these query reports?**
By dropping rows where `Customer Name` is null, because the `Grand Total`
footer leaves that column blank. It works on all four files today, but it is
an implicit contract with the export format - if the ERP ever writes a
footer with a populated customer, it leaks in. The robust version would
combine the null check with the date-pattern guard the data actually has
(`02-Apr-26` format) and an explicit assertion on row counts.

**Q6. You have 610 invoices and 37 sales orders. Does the code know that?**
No, and that is F-04. Every field called `orders` is
`Doc.No().nunique()` on the invoice frame, so `get_revenue_summary` reports
`unique_orders: 610` and `avg_order_value` as the mean invoice. The real
sales-order frame is read but only contributes a single sum
(`so['Grand Total']`) to one tool. The naming mismatch would surface as a
16.5x discrepancy the moment a user asked "average order value" and then
"how many orders did we get?".

**Q7. Why is week 17 missing and does it matter?**
The export window has an empty ISO week (19-Apr to 26-Apr 2026). Because the
trend axis is built from `sorted(df['week'].unique())`, week 17 does not
exist for any entity, so weeks 16 and 18 are fitted as adjacent points. The
8-day gap is invisible: slopes are computed as if the change happened in one
week. It matters most for entities whose entire signal falls across that
boundary.

### Analytics and correctness

**Q8. Explain the health score and defend it.**
40% revenue, 30% invoice frequency, 20% product diversity, 10% recency,
each min-max scaled against the largest customer, banded at 60/30. I would
defend the *shape* - it is transparent, cheap, and explainable, which
matters when you have to justify a recommendation to a sales head. I would
not defend the details: revenue-share normalisation means concentration and
health are the same number, recency is measured against the newest invoice
in the file rather than today (so it is a constant across a 28-day window),
frequency counts invoices rather than orders, and there is no payment
dimension at all even though the outstanding balance sits in a workbook
nobody loads. And 29 of 33 customers land in LOW, so the band structure
does not discriminate.

**Q9. A tool returns `gap_pct = -4.94e17`. Talk me through it.**
The formula is `gap / (so_revenue + 1e-9) * 100`. For the 26 customers who
appear only in the invoice export, `so_revenue` is zero after the outer
join, so we divide by `1e-9`. The epsilon converts a division by zero into a
large finite number instead of an exception - which is worse, because now it
looks like a value. Two layers are wrong: the arithmetic (a percentage
against a zero base should be null, not enormous) and the premise (there is
no order-to-invoice key, so even a correct percentage would not measure
fulfilment). The fix is to gate on `so_revenue > 0` *and* to stop claiming
the tool detects unfulfilled orders.

**Q10. `get_trend_direction` and `get_customer_deep_dive` disagree about
the same customer. Which is right?**
Neither, and that is the point. They pass differently-shaped series to the
same classifier. `get_trend_direction` zero-fills over the global week axis
- `[0, 306902, 235365, 0]` gives a slope of -5.3%, classified STABLE, and
then the row is dropped from the response entirely. The deep dive passes the
entity's own sparse groupby - `[306902, 235365]` - giving -26.4%,
classified DECLINING, and returns an "investigate satisfaction" action.
The classifier is not the problem; the preprocessing is duplicated and
inconsistent. One shared `weekly_series()` helper fixes it. The deeper issue
is that dropping STABLE means the user cannot see that 52 of 215 entities
were never reported.

**Q11. Is a single spike a growth trend?**
In this codebase, yes - and that is wrong. `_slope_label` fits a line and
normalises the slope by the series mean. For `[0, 0, 33028, 0]` the mean is
dragged down by three zeros, the slope is positive, and the entity is
returned as GROWING with a recommendation to increase focus. I verified this
on `Davic Ship Management`, whose entire revenue is one invoice in week 16.
The fix is a minimum-activity guard: require a minimum number of active
periods, or use a robust slope (Theil-Sen), or compare last-active-period
against the median of prior active periods rather than fitting across zeros.

**Q12. The tool calls a service charge "DEAD_STOCK". Why?**
`get_low_volume_analysis` sorts by summed quantity and stamps
`DEAD_STOCK` at `qty == 0`. `Delivery Courier Charges` has no quantity by
nature - it earned 60,970 across 43 invoices from 9 customers. Nothing
consults revenue, invoice count or item type before assigning the verdict.
It is a good example of a rule that is correct on its own terms and wrong on
its subject: quantity is not a meaningful dimension for every row in an
invoice line table.

### LLM and tooling

**Q13. Why tool calling rather than text-to-SQL?**
Three reasons. The corpus is structured and small, so a pandas groupby is
both faster and more predictable than a generated query. Generated SQL needs
a schema the model can misread, a sandbox, and error recovery; a function
schema with an enum is far harder to get wrong. And tool results are
typed dicts we control, so the model's second pass sees exactly the fields
we chose - which is what lets the "no invented data" rule actually hold.

**Q14. What does `MAX_ITERATIONS = 6` buy you, and what does it cost?**
It bounds worst-case latency and spend: at most six completion calls per
request, each with `max_tokens=16384`. The cost is that a genuinely
multi-step question - top-N, then a deep dive on the answer, then a
discontinuation check - can exhaust the budget and return
`"Agent reached max iterations without final answer."` with
`error: max_iterations_reached`, still as HTTP 200. Parallel tool calls in a
single message (`:273-298`) mitigate this: a model that asks three questions
at once spends one iteration, not three.

**Q15. The prompt says "do not invent data". Is that enough?**
No, and the code knows it - three of its nine rules are workarounds for tool
behaviour rather than business requirements. Prompt-level constraints are
probabilistic; schema-level constraints are not. The stronger controls here
are structural: the model can only obtain numbers from `TOOL_REGISTRY`, and
tool exceptions are contained as `{"error": ...}` rather than allowed to
become prose. What the prompt cannot fix is a tool that returns a wrong-but-
well-formed number, like `period: "01-Apr-2026 to 30-Apr-2026"` or
`unique_orders: 610`.

**Q16. `temperature=1`. Defend or change?**
Change it. The requirement asks for repeatability, and the deterministic half
of this system already delivers it. Setting temperature low (0-0.2) costs
almost nothing in answer quality for a task that is essentially "select a
tool and describe a table", and buys consistent framing across runs - which
matters when answers are going into a management review. If the reasoning
budget on the NVIDIA path needs headroom, that is what `reasoning_budget` is
for, not sampling variance.

**Q17. How would you add a new tool end to end?**
Four places, in order: write the function in `analytics_tools.py` and add it
to `TOOL_REGISTRY` (`:516`); add its schema to `TOOL_DEFINITIONS` in
`agent.py` (`:37`) - description quality matters more than the code here,
because it is what the model reads; if it needs new data, extend `DATA_FILES`
and `_clean` in `data_loader.py`; optionally add a quick-query button in
`index.html`. No routing, no ORM, no frontend state changes. The design
deliberately makes the tool surface the only extension point.

### Production readiness

**Q18. What would you do first to take this to production?**
Load the invoice header workbook - it is already in the repo and it unlocks
payment, outstanding and due-date analysis across three tools at once. Then
fix F-01 (gate the percentage, stop claiming fulfilment detection), extract
a shared weekly-series helper to kill F-03, and rename `orders` to
`invoice_count` everywhere so the model stops inheriting a lie. Separately:
move sessions to Redis or a database, because the in-memory dict is
guaranteed to misbehave on the platform this is deployed to; and move the
data out of git, because S-1 is the finding that would actually end a
conversation with a client.

**Q19. You have no tests. What is the first test you write?**
A golden-fixture test on `analytics_tools`: pin the four workbooks, snapshot
each of the 10 tools' output, and assert exact equality on the numeric
fields. It costs an afternoon and it would have caught F-01, F-03, F-07, F-11
and F-13 before they reached a document - all five were found by running
the tools once. Second: an invariant test that
`sum(get_trend_direction growing + declining + stable) == nunique(customers) + nunique(items)`,
which fails today at 163 vs 215.

**Q20. The demo mode answers are hardcoded. Is that a problem?**
Today they are accurate - I checked seven figures against live tool output
and all seven match. The problem is that they are literals in HTML with no
test, no generation step and no link to `data/`. The first data reload
silently turns demo mode into a source of confidently wrong numbers, and
demo mode is the entry point for anyone without a token. Generate them from
the tools at build time, or label them explicitly as an illustrative sample.

---

## 16. Appendix A - Source Index

| File | Lines | Role |
| --- | --- | --- |
| `index.html` | 917 | Frontend: CSS 8-499, markup 501-649, JS 651-915 |
| `llm_project/llm_api/analytics_tools.py` | 529 | 12 tools + `TOOL_REGISTRY` 516-529 |
| `llm_project/llm_api/agent.py` | 305 | System prompt 20-35, schema 37-182, client 210-228, loop 231-305 |
| `llm_project/llm_project/settings.py` | 198 | Env loader 20-35, providers 52-63, secrets 70-78, CORS 188-198 |
| `llm_project/llm_api/views.py` | 142 | Auth 15-28, sessions 30-31, 4 views 41-142 |
| `llm_project/llm_api/data_loader.py` | 89 | Data dir 9-15, file map 17-30, clean 49-56, cache 59-81 |
| `llm_project/llm_project/urls.py` | 37 | `_index_view` 25-30, routes 33-37 |
| `README.md` | 60 | Live URL 5, trial token 45, endpoints 51-56 |
| `llm_project/.env.example` | 60 | Providers 11-17, tokens 20-21, data 24-27, unused config 29-60 |
| `llm_project/llm_api/README.md` | 80 | **Stale** - documents `anthropic`, old filenames |
| `app.py` | 15 | Vercel WSGI entry |
| `manage.py` (root / inner) | 20 / 20 | Local dev entry |
| `vercel.json` | 14 | Build + catch-all rewrite |
| `.gitignore` | 227 | `.env` 151-153, `db.sqlite3` 61, legacy data 217-219 |
| `requirements.txt` (root / inner) | 8 / 8 | Identical: Django 5.2.7, cors, DRF, httpx, numpy, openai, openpyxl, pandas |
| `llm_project/llm_api/models.py` | 2 | Empty - no ORM models |
| `llm_project/llm_api/tests.py` | stub | No tests |
| `package-lock.json` | 86 bytes | Vestigial - no `package.json` |

**Git:** branch `main`, 16 commits, latest `9342263 docs: update live URL
and trial token`. Notable: `b2e9c96 feat: dual LLM providers selected via
auth token`, `53f1494 feat: NVIDIA AI provider, auth popup, rebrand to ERP AI
Analytics`, `8723e6e fix: catch-all rewrite to Django, serve index.html from
root view`.

---

## 17. Appendix B - Verified Figures, Consolidated

### 17.1 Data

| Quantity | Value |
| --- | --- |
| Workbooks in `data/` | 4 (211,365 bytes total), plus 4 gitignored copies in `llm_project/llm_api/data/` |
| Workbooks loaded | 3 |
| `so` / `sod` / `inv` shapes | 37x10 / 415x13 / 3333x13 |
| Invoice net (`inv.Amount`) | 10,408,405.39 |
| Invoice qty | 14,998 |
| Invoice docs | 610 |
| Invoice customers / items / categories | 33 / 182 / 46 |
| Order gross (`so.Grand Total`) | 5,106,918.32 |
| Order net (`so.Amt.Total`) | 4,549,969.80 |
| Order detail net (`sod.Amount`) | 4,264,965.68 |
| Orphan order value (net - detail) | 285,004.12 |
| Invoice weeks | 14, 15, 16, 18 |
| Order weeks | 14, 15, 16, 18, 19 |
| `half` split (invoice rows) | first 2,051 / second 1,282 |
| Whitespace-padded `Item Name` | 133 rows, 5 distinct |
| Header workbook | 611 rows, 610 docs; cols include `Outstanding Amount`, `Due Date` |

### 17.2 Revenue summary (tool output)

| Key | Value |
| --- | --- |
| `period` (hardcoded) | 01-Apr-2026 to 30-Apr-2026 |
| `total_invoiced_revenue` | 10,408,405.39 |
| `total_so_value` (gross) | 5,106,918.32 |
| `total_invoice_line_items` | 3,333 |
| `unique_customers` / `unique_products` / `unique_orders` | 33 / 182 / 610 |
| `avg_order_value` | 17,062.96 |
| `peak_week` | 15 |
| weekly | w14 972,988.28 / w15 6,988,992.75 / w16 2,435,550.36 / w18 10,874.00 |

### 17.3 Concentration

| Measure | Value |
| --- | --- |
| Top-5 customers share | 77.06% (top-5 revenue 8,020,782.53) |
| Top customer | Best Marine Exports, 4,942,870.53, 47.49% |
| Top product share | 11.13% (Boilersuit-~-MOL-StatSafe-Orange, 1,158,453.12) |
| Top category share | 43.82% (Boilersuit, 4,560,915.38) |
| Top-8 categories | 83.76% of revenue (8,718,504.70) |

### 17.4 Tool outputs

| Tool | Headline output |
| --- | --- |
| `get_top_n(customer,5)` | 47.49 / 10.40 / 8.49 / 5.46 / 5.21 % |
| `get_top_n(product,5)` | 11.13 / 5.34 / 4.82 / 3.29 / 3.28 % |
| `get_customer_health_scores` | 33 rows; HIGH 1, MEDIUM 3, LOW 29; range 2.74 - 69.29 |
| `get_discontinuation_candidates` | 13 products, 6 customers |
| `get_volume_growth_alerts` | 12 customers, 40 products, threshold 20%; top +333.40% |
| `get_trend_direction` | growing 39, declining 124, **dropped 52** of 215 |
| `get_order_to_invoice_analysis` | 38 rows; OVER 30, UNDER 7, MATCHED 1; max abs gap_pct 4.94287053e+17 |
| `get_low_volume_analysis` | 20 rows; DEAD_STOCK 2 (both service lines), VERY_LOW 18 |
| `get_customer_deep_dive('V.Ships')` | 542,267.00, 104 invoices, trend DECLINING, weeks {15,16} |
| `get_product_deep_dive('Boilersuit')` | 4,885,919.38, qty 4,060, 30 customers, trend DECLINING |
| `get_payment_behavior` | `DATA_NOT_AVAILABLE` |
| `get_return_analysis` | `DATA_NOT_AVAILABLE` |

### 17.5 `_slope_label` truth table (verified)

| Series | Label |
| --- | --- |
| `[10, 12, 14, 16]` | GROWING |
| `[10, 9, 11, 8]` | STABLE |
| `[5000, 0, 0, 0]` | DECLINING |
| `[0, 0, 0, 0]` | NO_ACTIVITY |
| `[0, 0, 33028, 0]` | GROWING (false positive) |
| `[0, 0, 0, 5000]` | GROWING (false positive) |
| `[306902, 235365]` (sparse, deep dive) | DECLINING |
| `[0, 306902, 235365, 0]` (zero-filled, trend tool) | STABLE |
| `[<1 element]` | INSUFFICIENT_DATA |

---

*End of document. Prepared by direct source reading and execution of
`llm_api.data_loader` and `llm_api.analytics_tools` against the repository's
own data. Django, the OpenAI client and the live deployment were not
executed; see 13.3.*




---

## Part III: ERP AI Analytics Operational README

*Reproduced verbatim from `ERP_README.md` (298 lines), with cross-file
references re-pointed at Parts I and II.*

---

# ERP AI Analytics

AI-powered sales-intelligence chatbot for **Best Marine Private Limited**. It
reads the four ERP Excel exports in `data/` (Sales Orders, Sales Order
Details, Sales Invoice Details), and answers ad-hoc business questions through
an LLM agent that calls a curated set of analytical tools.

**Live demo:** https://erp-2w694uaqf-erp-bot-demo.vercel.app/

> **Part III - operational README.** The implementation deep-dive
> (architecture, algorithms, verified figures, defect register F-01..F-21,
> security review S-1..S-8, interview Q&A) is **Part II** of this combined
> file; the HNS platform design specification is **Part I**.

---

## What it does

- **Conversational analytics** - ask in plain English, the agent picks tools and answers with tables/percentages.
- **Top N** customers, products, categories by revenue / qty / order count.
- **Customer health scores** (0-100, weighted) and **discontinuation candidates**.
- **Growth alerts** (first- vs second-half comparison) and **weekly trend direction** per customer/product.
- **Order-to-invoice fulfilment comparison** (known join defect - see Limitations).
- **Low-volume / slow-moving inventory**, **revenue summary**, and per-customer / per-product **deep dives**.
- Two honest **stubs** for payment behaviour and sales returns (data not present).

Current data scope: 37 orders, 415 order-detail lines, 3,333 invoice lines,
33 customers, 13 products, 46 categories - exports dated 01-Apr to 06-May-2026.

---

## Architecture

```mermaid
flowchart TB
    subgraph BROWSER["Browser - index.html (917 lines, vanilla JS)"]
        UI["Chat UI<br/>auth modal, markdown rendering"]
    end

    subgraph VC["Vercel - @vercel/python WSGI (app.py)"]
        subgraph DJ["Django 5.2.7 + DRF"]
            API["POST /api/ask/<br/>views.py:41"]
        end
        subgraph AG["llm_api.agent"]
            RUN["run_agent()<br/>6-iteration tool loop"]
        end
        subgraph TL["llm_api.analytics_tools"]
            REG["TOOL_REGISTRY<br/>12 tools"]
            LD["load_data()<br/>Excel -> cached DataFrames"]
        end
    end

    subgraph LLM["LLM provider"]
        NIM["NVIDIA NIM<br/>nvidia/nemotron-3-ultra-550b-a55b"]
        OAI["OpenAI (optional)"]
    end

    subgraph FS["data/ - 4 Excel workbooks, ~211 KB"]
        F1["Sales Order"]
        F2["Sales Order Details"]
        F3["Sales Invoice Details"]
        F4["Sales Invoice header (never loaded)"]
    end

    UI -->|Bearer token| API
    API --> RUN
    RUN --> REG --> LD --> FS
    RUN --> NIM
    RUN --> OAI
```

The agent loop: send user query + 12 tool definitions to the LLM, execute any
`tool_calls` against `TOOL_REGISTRY`, feed results back, repeat until the model
answers or 6 iterations are exhausted (`max_tokens=16384`).

---

## Tech stack

| Layer | Choice |
| --- | --- |
| Frontend | Single-file vanilla HTML/CSS/JS, no framework, no build step (`index.html`, 917 lines) |
| Backend | Django 5.2.7 + Django REST Framework, single WSGI app |
| Agent | OpenAI Python SDK in OpenAI-compatible mode (`httpx`) |
| LLM | NVIDIA NIM `nvidia/nemotron-3-ultra-550b-a55b` (OpenAI optional) |
| Data | pandas + openpyxl, in-memory cache behind a threading lock |
| Deployment | Vercel (`@vercel/python`) |

Python 3.12 is pinned in `.python-version`. Dependencies (8) are in the root
`requirements.txt` (identical copy under `llm_project/`).

---

## Repository layout

```
erp-bot/
├─ app.py                    Vercel WSGI entry point
├─ manage.py                 repo-root Django dev entry (chdirs into llm_project/)
├─ index.html                the entire frontend
├─ requirements.txt          Python dependencies
├─ vercel.json               build + catch-all rewrite to /app.py
├─ .python-version           3.12
├─ .gitignore                227 lines
├─ data/                     the 4 ERP Excel exports (~211 KB) - see Data below
├─ README.md                 this combined file (Parts I-III)
└─ llm_project/
   ├─ .env.example           documented env-var template
   ├─ manage.py
   ├─ llm_api/               the application
   │  ├─ agent.py            LLM tool-loop agent (305 lines)
   │  ├─ analytics_tools.py  12 analytical tools (529 lines)
   │  ├─ data_loader.py      Excel -> DataFrame loading + cache (89 lines)
   │  ├─ views.py            auth + 4 API views (142 lines)
   │  └─ urls.py             /api/ routes
   └─ llm_project/           Django project (settings.py, urls.py, wsgi.py)
```

---

## Data

The app loads **three** of the four workbooks (`data_loader.py:17-30`). The
fourth (Sales Invoice **header**) is shipped but not ingested - defect
**F-02** (see Part II).

| File (`data/`) | Rows after load | Bytes | Loaded |
| --- | --- | --- | --- |
| Sales Order - DynaRep_Best Marine..._2026-04-01_2026-05-16_Date Wise Sales Order.xlsx | 37 | 7,015 | yes |
| Sales Order Details - DynaRep_...__Submitted + Draft_Date Wise Sales Order.xlsx | 415 | 24,114 | yes |
| Sales Invoice Details - DynaRep_..._Sales Invoice_Submitted + Draft_...xlsx | 3,333 | 151,321 | yes |
| Sales Invoice - DynaRep_..._Sales Invoice_Submitted + Draft_...xlsx | (header; 611 rows) | 28,915 | no |

Files resolve against `data/` automatically. If you change the files on disk,
call `POST /api/reload-data/` (or restart) to refresh the in-memory cache.

---

## Quick start

```bash
git clone https://github.com/nachiiiket/erp-bot.git
cd erp-bot
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create `llm_project/.env` from `llm_project/.env.example` at minimum:

```ini
NVIDIA_API_KEY=nvapi-...        # from https://build.nvidia.com
DJANGO_SECRET_KEY=<generated>   # python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

> **Data directory - read this before editing `.env`.**
> `data_loader.py` reads `SALES_DATA_DIR` at import time and, when set, treats
> it as an **absolute path** or as a path **relative to the current working
> directory**. `manage.py` runs Django with the working directory set to
> `llm_project/`, so `SALES_DATA_DIR=data` (the value in `.env.example`)
> resolves to `llm_project/data/` - which does **not** exist - and every tool
> fails with file-not-found. A leftover `SALES_DATA_DIR=` (empty) line has the
> same effect.
> **Fix: leave `SALES_DATA_DIR` commented out / deleted** (the default points
> at the repo-root `data/` and works from any directory), **or** set it to an
> absolute path. 

Run:

```bash
python manage.py runserver      # from repo root
```

Open http://localhost:8000 - the Django root route serves `index.html`. Enter
an auth token in the popup and start querying.

---

## Auth tokens

Every `/api/*` request must carry `Authorization: Bearer <token>`. The token
also **selects the LLM provider** (`views.py:15-28`).

| Environment var | Example | Provider selected |
| --- | --- | --- |
| `NVIDIA_AUTH_TOKEN` | `nv-token-2603` (shared demo token) | NVIDIA NIM |
| `OPENAI_AUTH_TOKEN` | `sk-...` | OpenAI |

If a token matches neither, the API returns `401 {"error": "Unauthorized"}`.
`nv-token-2603` is the published demo token baked into the live frontend -
rotate it for any shared or production deployment.

---

## API endpoints

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/ask/` | Run the agent. Body `{"query": "...", "session_id": "..."}` |
| GET | `/api/health/` | `{"status": "ok", "data": {sales_orders, order_details, invoice_lines}}` |
| POST | `/api/reload-data/` | Re-read the Excel files from disk, returns new row counts |
| DELETE | `/api/session/<session_id>/` | Drop one conversation history |
| GET | `/` | Serves the chat frontend (`index.html`) |

Example:

```bash
curl -X POST http://localhost:8000/api/ask/ \
  -H "Authorization: Bearer nv-token-2603" \
  -H "Content-Type: application/json" \
  -d '{"query": "Top 5 customers by revenue", "session_id": "demo"}'
```

Returns `{ "answer", "tools_used", "session_id", "error" }`. Conversation
history is kept in an in-memory dict (`_sessions`, capped at 20 messages / 10
exchanges per session id); multi-turn context is enabled by passing the same
`session_id`.

---

## Tools the agent can call

Defined in `analytics_tools.py`, exposed as OpenAI tool definitions in
`agent.py:37-182`. All are parameterised by the model.

| # | Tool | Serves |
| --- | --- | --- |
| 1 | `get_top_n` | Top N customers/products by revenue, qty or orders |
| 2 | `get_customer_health_scores` | Weighted 0-100 health score per customer |
| 3 | `get_discontinuation_candidates` | Products/customers to discontinue |
| 4 | `get_volume_growth_alerts` | First- vs second-half revenue/qty growth |
| 5 | `get_trend_direction` | Weekly revenue trend per customer/product |
| 6 | `get_order_to_invoice_analysis` | Order vs invoiced revenue per customer |
| 7 | `get_low_volume_analysis` | Bottom N products by qty (slow movers) |
| 8 | `get_revenue_summary` | Whole-business summary |
| 9 | `get_customer_deep_dive` | Customer view: orders, products, trend, health |
| 10 | `get_product_deep_dive` | Product view: customers, revenue, qty, trend |
| 11 | `get_payment_behavior` | **Stub** - payment data not uploaded |
| 12 | `get_return_analysis` | **Stub** - returns data not uploaded |

---

## Deploy to Vercel

1. Push `main` to GitHub (`https://github.com/nachiiiket/erp-bot`) - Vercel
   auto-deploys every commit (`vercel.json`: build `app.py` with
   `@vercel/python`, rewrite `/(.*)` to `/app.py`).
2. In the Vercel dashboard set the same env vars as in `.env`, plus a real
   `DJANGO_SECRET_KEY` (**never** commit `.env`).
3. Note: on serverless the `data/` workbooks are bundled read-only at build
   time - you cannot hot-replace them in the running app; `reload-data/` only
   re-reads the bundled copies.

---

## Known limitations

- **F-01**: `get_order_to_invoice_analysis` joins orders to invoices purely on
  customer name and divides by `so_revenue + 1e-9`; 31 of 38 rows have an
  empty join side and the tool reports values up to `4.9e17%` instead of a
  clean answer.
- **F-03 / F-05**: trend answers are contradictory between
  `get_customer_deep_dive` and `get_trend_direction`; 52 of 215 entities are
  silently dropped.
- **F-02**: the invoice-header workbook (dates, due dates, outstanding
  amounts) is never loaded, so payment-latency/debtor analysis is impossible.
- Two of the twelve tools are honest stubs; the requirement's regional,
  bottleneck, confidence and churn analyses are absent.
- No automated tests (`tests.py` is the vanilla Django stub); the agent/tools
  were validated by direct execution of every tool and by diffing the demo's
  canned answers against live outputs.
- LLM quality is untuned: `temperature=1`, `top_p=0.95`, no guardrails, 6
  iterations cap.

Full defect register (F-01..F-21), security review (S-1..S-8), risk register,
and verified numbers are in **Part II** of this file.

---

## Security notes

- The four ERP workbooks (~211 KB of real business data) are **tracked in this
  public repository** (`data/*.xlsx`). Remove them and rotate any credentials
  before wider distribution. `.gitignore` guards a legacy path only.
- The demo auth token is published here and in the frontend; cut a fresh
  `NVIDIA_AUTH_TOKEN` (and add an OpenAI one) for anything beyond the demo.
- `DJANGO_SECRET_KEY` silently falls back to a per-startup random value, which
  invalidates sessions on restart - set it explicitly in Vercel.
- Sessions are a shared in-memory dict: no TTL, unbounded growth, no isolation
  between concurrent users.

---

## Further reading

- **Part I** - HNS platform design specification (requirement-driven design).
- **Part II** - full implementation deep-dive: architecture, algorithm
  walkthroughs, 12-tool catalogue, agent loop, API/auth details, defect
  register (F-01..F-21), security review (S-1..S-8), measured timings,
  interview Q&A (20 items), verified figures appendix.