# Decisions (git-tracked, shared)

Architectural decisions and rationale. One line per entry.

Format: `[YYYY-MM-DD] Decision: <description> — Reason: <why>`

<!-- Entries below -->

[2026-06-25] Decision: Use Chroma (local file DB) instead of Pinecone — Reason: MVP demo needs zero-ops, no cloud dependency. Migrate to Pinecone/Qdrant post-MVP if needed.
[2026-06-25] Decision: Use DeepSeek Embedding API instead of OpenAI — Reason: Client already holds DeepSeek API Key. OpenAI-compatible protocol, zero migration cost.
[2026-06-25] Decision: Use Claude API via DeepSeek Pro proxy — Reason: Client accesses Claude through DeepSeek infrastructure. Design supports both Anthropic SDK and OpenAI-compatible modes.
[2026-06-25] Decision: Apple-style UI (glassmorphism, SF Pro font stack, spring animations) — Reason: Client demo requires high visual quality. Apple HIG design language for professional feel.
[2026-06-25] Decision: JSONL file for feedback storage — Reason: MVP data volume is minimal. No database needed. Upgrade to Postgres/ClickHouse post-MVP.
[2026-06-25] Decision: Two-layer rejection detection (keyword pre-check + prompt rule) — Reason: Prevent investment advice/stock prediction at both input gate and LLM level.
[2026-06-25] Decision: Recursive chunking for PDF ingestion (merge short paras, split long ones) — Reason: Balance semantic integrity with chunk size limits (100-1500 chars).
[2026-06-25] Decision: Session timeout at 10 min, clear history but keep session — Reason: User returning after timeout gets "new conversation" feel without reconnecting.
[2026-06-25] Decision: Cache recent 3 rounds of dialogue in memory (no vectorization) — Reason: Token budget sufficient for MVP. No persistence needed (sessions lost on restart is acceptable).
[2026-06-25] Decision: WebSocket as primary API, REST as fallback — Reason: Streaming UX requires WS. REST /api/chat provided for non-interactive integrations.
