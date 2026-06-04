# Integrity SDK v2.1 🛡️

The Foundational Cryptographic Identity, Trust, and Cognitive Safety SDK for Autonomous AI Agents. **v2.1: High-Fidelity Measurement Apparatus.**

Integrate mathematically verifiable behavior and hardware-attested provenance into your agent harnesses using high-throughput OpenTelemetry instrumentation.

---

## v2.1: High-Fidelity Measurement Apparatus

The v2.1 release establishes a high-fidelity observation layer, enabling deep visibility into an agent's internal decision boundaries and its macroscopic host interactions.

## 🚀 Advanced Agentic Capabilities

The Integrity SDK now supports a fully modular and multi-layered approach to agent trust:

- **BCC (Behavioral Commitment Chain)**: Cryptographically binds agent intent to actual execution, preventing intent drift.
- **World Awareness**: Secure data ingestion via the `WorldDataFetcher`, incorporating Proof of Provenance.
- **ZK-ML Verification**: Native integration for submitting Proof of Inference (PoI) to prove the integrity of the inference logic.
- **Cross-Chain Synchronization**: Native hooks for propagating reputation states across multiple blockchains via CCIP/LayerZero.

---

## Features

- **High-Throughput OTLP/gRPC Transport**: Persistent HTTP/2 connections with auto-fallback to OTLP/HTTP.
- **SQLite Offline Cache Fallback**: Seamlessly queues signed telemetry inside local DB (`~/.integrity/offline_moat.db`) when connection is down and auto-syncs when online, guaranteeing zero data loss.
- **Hardware-Anchored Provenance**: Automatically hashes system indicators (CPU ID, MAC, Machine ID) into W3C-compliant DID Documents.
- **Local Cognitive Metrology**: Enriched spans capturing token logprobability entropy, context grounding, and RAG alignment scores.
- **Universal Model Context Protocol (MCP)**: Native JSON-RPC server with tool-call tracing.

---

## Advanced Composite Risk Scoring

The SDK v2.1 introduces a correlation layer that combines microscopic inference signals with macroscopic host telemetry to compute 7 advanced risk scores:

| Signal | Logic |
| :--- | :--- |
| **Reconnaissance Risk** | Correlates tool-use patterns with file-access entropy. |
| **Compute Substitution** | Detects model-spoofing by analyzing inference latency jitter. |
| **Cognitive Fatigue** | Tracks ground-truth decay over a continuous agent session. |
| **Lateral Movement Prob** | Analyzes network connection entropy vs. model intent signals. |
| **Energy Efficiency** | Monitors compute/token-output efficiency to identify logic loops. |
| **Semantic Contradiction** | Flags discrepancies between tool output and model interpretation. |
| **Workspace Blast Radius** | Quantifies the potential system impact of tool-triggered file writes. |

---

## Data Collection & Privacy: The Observation Boundary

A critical distinction of the Integrity SDK is its focus on **Behavioral Observation** rather than additional content scraping.

### 1. Zero-Additional-Content Policy
The SDK **does not collect or store any additional raw inference data** (prompts or completions) beyond what is already passing through your frontier providers (OpenAI, Anthropic, etc.) during standard API usage. It simply intercepts and "seals" the existing data stream with cryptographic provenance.

### 2. The Unique Observation Layer
While frontier providers see the *content* of the conversation, they are blind to the *context* of the execution. The Integrity SDK collects unique telemetry that providers literally cannot see:
- **Macroscopic Host Telemetry**: Frontier providers don't know if an agent is exfiltrating your local files or scanning your internal network. The SDK monitors **Storage Flux** and **Network Flow** locally to verify the agent's actual impact on your system.
- **Hardware-Anchored Provenance**: While providers see an API key, the SDK binds the execution to a unique **Hardware Fingerprint (DID)**. This ensures that the agent's "soul" is tied to a specific physical unit, enabling non-repudiation and institutional accountability.

---

## Installation

Install the isolated library directly via pip:

```bash
pip install ./integrity-sdk
```

---

## SQLite Offline Cache & HMAC Security Protocol

If the target `integrity-oracle` becomes unreachable, the client redirects all queued telemetry into the local SQLite database to prevent any metric loss:
- **Database Path**: `~/.integrity/offline_moat.db`
- **Crypto Protection (HMAC-SHA256)**: Every row written to SQLite is bound to a cryptographic HMAC signature generated using the secret seed derived from the agent's private DID key:
  $$\text{integrity\_hash} = \text{HMAC-SHA256}(\text{payload\_str}, \text{private\_key})$$
- **Automatic Sync**: A background sync worker polls the Oracle every 10 seconds. Once back online, it validates row HMAC hashes (to detect database file tampering) and uploads verified payloads.

---

## Quickstart

### 1. Universal Framework Wrapping (v2.0)
The v2.0 SDK features a **Universal Facade** that automatically detects your framework (OpenAI, LangChain, Hermes, or custom harnesses) and applies cryptographic hooks.

```python
from integrity_sdk import Integrity

# 1. Initialize the global protocol connection
Integrity.init(
    agent_id="agent_quant_trader_01",
    oracle_url="http://localhost:8080/v1/transactions/report",
    extra_metadata={"alias": "Xibalba Master Node"}
)

# 2. Wrap your existing client or agent object
# Works with OpenAI, LangChain, or Antigravity MoE Agents
my_agent = Integrity.wrap(existing_client)

# Every subsequent action is now cryptographically anchored.
```

### 2. Manual Client Usage
For low-level control or custom event logging:


```python
from integrity_sdk import IntegrityClient

client = IntegrityClient(agent_id="my_custom_agent")

# Log telemetry event asynchronously
client.log_telemetry(
    metadata={"action": "sweep_yield", "vault_address": "0x123..."},
    zk_proof="0xabc123...", # generated locally via Noir prover
    batch_size=1,
    avg_entropy=0.15,
    avg_grounding=0.98
)
```

### 3. Human-in-the-Loop (HITL) Override Tracking
Capture manual interventions, latency, overrides, and calculate Levenshtein edit distance deltas automatically:

```python
client.log_hitl_action(
    action_type="override", # 'approval', 'rejection', 'override'
    proposed_content="Buy 10 AAPL",
    final_content="Buy 15 AAPL",
    reviewer_did="did:xibalba:human_operator_42",
    review_latency_ms=1250.0,
    justification="Insufficient liquidity depth",
    extra_metadata={"order_id": "tx_9921"}
)
```

### 4. Universal MCP Server Setup (For Non-Programmers)
To bind the Integrity shield to your no-code agent workspaces (e.g. Cursor or Claude Desktop), add the server command to your local MCP settings:

```json
{
  "mcpServers": {
    "integrity-shield": {
      "command": "python3",
      "args": ["-m", "integrity_sdk.mcp_server"],
      "env": {
        "INTEGRITY_AGENT_ID": "cursor_agent_shield"
      }
    }
  }
}
```

---

## Multi-Agent & Sub-Agent Context Isolation

The SDK supports running multiple distinct agents on a single machine without state or cryptographic key collisions.

### 1. Independent Agents
For completely unrelated agents running on the same hardware, the SDK provides isolation at two levels:
* **Directory-Based Workspace Isolation**: The SDK resolves config and credentials relative to the current working directory (CWD), building unique keys inside `.integrity/did/{agent_id}/`.
* **Process-Level Offline Moats**: Each agent logs to a separate namespaced SQLite cache file: `~/.integrity/offline_moat_{agent_id}.db`.
* **Identity Resolution**: The Oracle registers them as separate entities under the same physical machine:
  `did:xibalba:<hardware_fingerprint>:<agent_id>`

To run independent agents out of the same directory, use the environment override:
```bash
export INTEGRITY_AGENT_ID="MyIndependentAgent"
```

### 2. Hierarchical Sub-Agents
If a parent agent spawns a child sub-agent, they share a cryptographic hierarchy. Use the `spawn_subagent` interface:
```python
sub_client = client.spawn_subagent("ScreenerSubagent")
```
This automatically structures the child's identifier using hierarchical dot-notation:
`did:xibalba:<hardware_fingerprint>:<parent_id>.<subagent_id>`

---

## Wiki Documentation

For in-depth explanations of architectural primitives, cryptographic envelopes, and metrics metrology, explore our comprehensive wiki:
- [Wiki Home](wiki/Home.md)
- [System Architecture & Provenance](wiki/Architecture.md)
- [Developer Guide & API Reference](wiki/Developer-Guide.md)
- [Cognitive Local Metrology Heuristics](wiki/Local-Metrology.md)
- [Universal Model Context Protocol (MCP) Guide](wiki/MCP-Integration.md)
