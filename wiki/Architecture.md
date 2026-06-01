# System Architecture & Cryptographic Provenance 🛡️

The Integrity SDK acts as a **Zero-Trust Client Cryptographic Gateway** running on the host node of an autonomous agent. Its primary purpose is to establish identity non-repudiation and compile sensitive inference metadata into secure, verifiable spatial envelopes without introducing noticeable pipeline latency.

---

## 1. Hardware Fingerprinting & Provenance Engine

To prevent rogues or malicious processes from spoofing telemetry or copying an agent's on-chain stake registration, the SDK extracts immutable hardware bounds to establish physical provenance:

1. **System Attributes Extracted**:
   - **Machine ID**: Extracted from `/etc/machine-id` or `/var/lib/dbus/machine-id` to identify OS installations.
   - **MAC Address**: Retreived from active network adapters to bind local network presence.
   - **Hostname**: Captured to contextualize the server name.
   - **CPU Model**: Extracted via `/proc/cpuinfo` to establish execution capabilities.

2. **The Fingerprint Hash**:
   The attributes are canonicalized, concatenated, and hashed using deterministically salted **SHA-256**, generating a unique 64-character fingerprint:
   $$\text{Fingerprint} = \text{SHA256}(\text{MachineID} \parallel \text{MAC} \parallel \text{CPU} \parallel \text{Hostname})$$

3. **Deterministic Key Generation**:
   The fingerprint serves as a deterministic seed to generate a cryptographically secure **Ed25519** keypair.

---

## 2. W3C DID Document Structure

The generated public key is encapsulated into a standard W3C-compliant Decentralized Identifier (DID) Document.

- **DID URI Scheme**: `did:integrity:<fingerprint>`
- **Example Document**:
  ```json
  {
    "@context": "https://www.w3.org/ns/did/v1",
    "id": "did:integrity:52f9ea2197fd0e039...",
    "verificationMethod": [
      {
        "id": "did:integrity:52f9ea2197fd0e039...#key-1",
        "type": "Ed25519VerificationKey2020",
        "controller": "did:integrity:52f9ea2197fd0e039...",
        "publicKeyMultibase": "z6MkmF17..."
      }
    ],
    "authentication": [
      "did:integrity:52f9ea2197fd0e039...#key-1"
    ]
  }
  ```

---

## 3. Asynchronous Spatial Envelopes (Batcher)

To keep API latency under sub-millisecond thresholds:
1. When inference occurs, raw metrics are pushed onto an in-memory **thread-safe queue**.
2. A dedicated background **daemon thread** runs a continuous loop.
3. Every time the queue reaches its `batch_size_limit` (default: 50) or the `flush_interval_sec` (default: 5s) expires, the background worker flushes the queue.
4. The worker bundles the telemetry items, assigns a strictly monotonic, locally-cached timestamp **nonce** to prevent replay vectors, and signs the canonical JSON string with the Ed25519 private key.

---

## 4. SQLite Offline Cache Fallback

To prevent data loss or score drawdowns when the network is unstable or the Oracle is offline:
1. If the background HTTP request to `/ingest` throws a connection exception, the SDK catches the error.
2. The signed, cryptographically intact spatial envelope is immediately serialized and persisted into a local SQLite database located at `~/.integrity/offline_moat.db`.
3. A background sync thread polls the Oracle every 10 seconds.
4. Upon network restoration, the background thread automatically drains and uploads the cached backlog, ensuring **100% historical provenance and AIS metrics consistency**.

---

## 4. Zero-Knowledge Integration

The SDK implements the Aztec Noir prover framework:
- Private inputs (such as prompt texts or fine-grained token logprobabilities) never leave the local machine.
- The SDK compiles the private inputs using Noir local WASM or FFI bindings, computing mathematical safety metrics.
- Only the cryptographic **ZK Proof** is packaged and sent in the telemetry payload, allowing third-party auditors to verify that safety scores were honestly computed without ever reading raw text!
