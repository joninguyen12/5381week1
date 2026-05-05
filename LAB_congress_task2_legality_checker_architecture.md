# LAB Congress — Task 2: Architecture (Legality Checker / Option A)

Mermaid diagram for the **Legality Checker** focal agent: legal corpora, hybrid retrieval, tiered access, and RAG into the structured-assessment prompt.

---

## Architecture diagram

```mermaid
flowchart TB
    subgraph ingest["Document ingestion"]
        S1["Statutes & session law<br>U.S. Code, enrolled bills"]
        S2["Regulations<br>CFR, Federal Register"]
        S3["Case law<br>opinions PDF/HTML"]
        S4["Secondary analysis<br>CRS-style memos, annotated Constitution"]
        S5["Chamber material<br>rules, precedents (if in scope)"]
    end

    ingest --> P["Pipeline: extract text → normalize citations<br>→ citation-aware + semantic chunking"]
    P --> E["Embedder<br>e.g. text-embedding-3-large or domain-legal model"]
    P --> SUM["Optional: per-document summaries<br>for routing / display only"]

    E --> V[("Postgres + pgvector<br>chunks + embeddings + metadata")]
    SUM --> V
    P --> R[("Object store<br>S3 / Azure Blob — raw PDFs & source files")]

    subgraph meta["Metadata on every chunk (for RLS & filters)"]
        M1["clearance: public | staff | committee | classified"]
        M2["source_type, jurisdiction, effective_date"]
        M3["citation_spans / section paths"]
    end
    V --- meta
    R --- meta

    U["Staff user + JWT / SSO<br>clearance claims"] --> API["API gateway<br>policy: max clearance = user tier"]
    API --> RET["Retriever: hybrid search<br>metadata filters + vector similarity"]
    V --> RET
    R -.->|"signed URL only if<br>chunk row allowed"| RET

    RET --> AC{"Row-level security (RLS)<br>chunk.clearance ≤ user.clearance"}
    AC -->|"allowed rows only"| CTX["Retrieved context package<br>top-k chunks + source pointers"]
    AC -->|"no qualifying rows"| EMPTY["Empty / withheld context<br>(no leak of existence)"]

    CTX --> AG["Legality Checker agent<br>system prompt: cite only retrieved text"]
    EMPTY --> AG
    PROP["User: proposed action text"] --> AG

    AG --> OUT["Structured output<br>issues, citations inventory, confidence"]

    subgraph agent_rules["Agent sees only"]
        A1["Retrieved chunks + summaries<br>passed in this request"]
        A2["NOT full corpus or raw stores"]
    end
    AG --- agent_rules
```

---

## Design questions (concise)

| Question | Choice for this system |
|----------|-------------------------|
| **Ingestion & chunking** | Ingest **legislative text, statutes, regs, opinions, secondary memos** (not constituent mail as a primary source for legality). **Chunk** with **citation-aware boundaries** (sections, syllabi, paragraph breaks) plus **semantic windows**; store **optional summaries** for routing/UI, not as sole evidence for “clearly legal/illegal.” |
| **Access control** | **Database-enforced RLS** on chunk/document rows by **clearance tier**; API maps SSO/JWT to max tier. Prefer **filtering at query time** so the model never receives withheld text. |
| **Where vectors vs raw live** | **Vectors + chunk text + metadata** in **Postgres/pgvector**; **original PDFs/files** in **object storage** with **same clearance metadata**; retrieval returns chunk text; raw fetch only via **short-lived signed URLs** after RLS passes. |
| **What the agent sees** | **Only retrieved chunks (and optional short summaries of those docs)** in the prompt for that turn—not the full DB or arbitrary raw files. |
| **Query above clearance** | **RLS excludes rows**; retriever returns **empty or degraded context**; agent must answer with **legally uncertain / outside my knowledge** and **no inference** from missing data. Optionally return **403** at API for obviously mis-scoped requests without revealing labels. |

---

← [Lab handout: `LAB_congress.md`](LAB_congress.md)
