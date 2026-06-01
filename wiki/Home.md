# Integrity Protocol SDK Wiki 📖

Welcome to the official developer and systems architecture wiki for the **Integrity Protocol SDK**. 

The Integrity SDK acts as the local **Cryptographic Prover and Spatial Envelope Generator** that secures and binds autonomous AI agent behavior to institutional accountability frameworks.

---

## Wiki Portals

### 🛡️ [System Architecture & Cryptographic Provenance](Architecture.md)
Explore the mathematical underpinning of the Identity and Provenance engine:
- Hardware-bound fingerprinting (CPU, MAC, Machine ID hashes).
- W3C-compliant DID Document structures (`did:integrity:<fingerprint>`).
- Cryptographic spatial envelope signatures and replay-attack mitigations.
- Integration bounds with local Aztec Noir Zero-Knowledge (ZK) provers.

### 🧠 [Local Cognitive Metrology Heuristics](Local-Metrology.md)
Discover how the SDK independently monitors model cognitive safety statistics directly on the edge host:
- Local token logprobability entropy & repetition metrics.
-sliding-window context grounding calculations (RAG alignment).
- Heuristic task completion and safety bounds.

### 🔌 [Universal Model Context Protocol (MCP) Guide](MCP-Integration.md)
Enable frictionless cryptographic trust anchoring for non-programmers:
- Adding the MCP server to Claude Desktop.
- Setting up the MCP server inside Cursor.
- Tool mappings, inputs, outputs, and JSON-RPC structures.

### 🛠️ [Developer Guide & API Reference](Developer-Guide.md)
Explore complete developer references, error handling strategies, and SQLite caching protocols:
- `IntegrityClient` and `IntegrityOpenAI` API parameter references.
- Local SQLite database WAL caching mechanics and HMAC-SHA256 tamper checks.
- Process ID padding metrics to prevent distributed concurrency lockouts.
