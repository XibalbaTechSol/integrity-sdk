# Integrity SDK 🛡️

The Foundational Cryptographic Identity, Trust, and Cognitive Safety SDK for Autonomous AI Agents. 

Integrate mathematically verifiable behavior and hardware-attested provenance into your agent harnesses with a **single line of code**.

---

## Features

- **Sub-Millisecond Asynchronous Telemetry**: Non-blocking concurrent worker architecture ensures zero added latency during LLM inference.
- **SQLite Offline Cache Fallback**: Seamlessly queues signed telemetry inside local DB (`~/.integrity/offline_moat.db`) when connection is down and auto-syncs when online, guaranteeing zero data loss.
- **Hardware-Anchored Provenance**: Automatically hashes system indicators (CPU ID, MAC, Machine ID) into W3C-compliant DID Documents (`did:integrity:<fingerprint>`).
- **Autonomous DID Registration**: Cryptographically handshakes and binds identities via the `integrity-oracle` on initialization.
- **Local Cognitive Metrology**: Independently monitors token logprobability entropy, context grounding, and goal completion state on the client edge.
- **Universal Model Context Protocol (MCP)**: Native JSON-RPC server enabling non-programmers to wrap Cursor or Claude Desktop configurations.

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

### 1. Zero-Friction OpenAI client Wrapping (Python)
Integrate cryptographic shield logging with your standard OpenAI workflows seamlessly:

```python
from integrity_sdk import IntegrityOpenAI

# Single-line integration wrapper
client = IntegrityOpenAI(agent_id="agent_quant_trader_01")

# Standard inference pipeline — completely unchanged!
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Sweep USDC yield margins on Base L2."}]
)

print(response.choices[0].message.content)
```

### 2. Native Client Usage
For custom agent harnesses or manual event logging:

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

### 3. Universal MCP Server Setup (For Non-Programmers)
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
