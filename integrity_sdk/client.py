import json
import requests
import threading
import time
import os
from typing import Optional, Any

from .batcher import TelemetryBatcher
from .prover import NoirProver


class IntegrityClient:
    """
    Main entry point for Edge Agents to interact with the Integrity Protocol.
    Manages background batching, DID-based signing, and async submission
    to the Axum Oracle.
    """
    def __init__(
        self,
        agent_id: Optional[str] = None,
        oracle_url: str = "http://localhost:3001/ingest",
        batch_size_limit: int = 50,
        flush_interval_sec: float = 5.0,
        did: Optional[str] = None,
        subagent_id: Optional[str] = None,
        enable_full_recording: bool = False,
    ):
        # Resolve agent_id: parameter -> env variable -> script name -> directory name -> username fallback
        self.agent_id = agent_id or os.getenv("INTEGRITY_AGENT_ID")
        if not self.agent_id:
            try:
                import sys
                main_file = sys.argv[0]
                if main_file:
                    base_name = os.path.basename(main_file)
                    name_without_ext = os.path.splitext(base_name)[0]
                    # Filter out interactive/wrapper commands
                    if name_without_ext and name_without_ext not in ("-c", "ipython", "poetry", "uv", "pip", "setup"):
                        self.agent_id = name_without_ext
            except Exception:
                pass

        if not self.agent_id:
            try:
                cwd_name = os.path.basename(os.getcwd())
                if cwd_name:
                    self.agent_id = cwd_name
            except Exception:
                pass

        if not self.agent_id:
            try:
                import getpass
                self.agent_id = f"agent_{getpass.getuser()}"
            except Exception:
                self.agent_id = "default_agent"

        self.subagent_id = subagent_id
        self.enable_full_recording = enable_full_recording
        self.oracle_url = oracle_url
        self.batcher = TelemetryBatcher(
            batch_size_limit=batch_size_limit,
            flush_interval_sec=flush_interval_sec,
        )
        self.prover = NoirProver(agent_id=self.agent_id)

        # ---- DID / hardware binding ----------------------------------
        self._did: Optional[str] = did
        self._keypair = None
        self._hardware_fingerprint: Optional[str] = None
        self._evm_address: Optional[str] = None
        self._owner_address: Optional[str] = None

        try:
            from .did import load_or_create_did, get_hardware_fingerprint, derive_evm_address

            if self._did is None:
                self._did, self._keypair = load_or_create_did(self.agent_id)
            else:
                _, self._keypair = load_or_create_did(self.agent_id)

            self._hardware_fingerprint = get_hardware_fingerprint()

            # Derive a secure HMAC secret from DID keypair to lock local SQLite database against offline tampering
            if self._keypair is not None:
                if hasattr(self._keypair, "private_bytes_raw"):
                    self._hmac_secret = self._keypair.private_bytes_raw()
                else:
                    try:
                        from cryptography.hazmat.primitives import serialization
                        self._hmac_secret = self._keypair.private_bytes(
                            encoding=serialization.Encoding.Raw,
                            format=serialization.PrivateFormat.Raw,
                            encryption_algorithm=serialization.NoEncryption()
                        )
                    except Exception:
                        self._hmac_secret = b"integrity_protocol_sqlite_cache_shared_secret"

                # Derive deterministic EVM (Secp256k1) address from the master seed
                try:
                    seed_bytes = self._hmac_secret  # same 32-byte seed
                    self._evm_address = derive_evm_address(seed_bytes)
                    print(f"[IntegrityClient] Derived EVM address: {self._evm_address}")
                except Exception as evm_exc:
                    print(f"[IntegrityClient] EVM address derivation skipped: {evm_exc}")
            else:
                self._hmac_secret = b"integrity_protocol_sqlite_cache_shared_secret"
        except Exception as exc:
            # DID subsystem is best-effort; agent must not crash if
            # hardware reads or key generation fail.
            self._hmac_secret = b"integrity_protocol_sqlite_cache_shared_secret"
            print(f"[IntegrityClient] DID init skipped: {exc}")

        self.last_model = None
        self.last_provider = None
        self._lock = threading.Lock()

        self._running = True
        self._init_sqlite_cache()
        self._worker_thread = threading.Thread(
            target=self._background_worker, daemon=True
        )
        self._worker_thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def did(self) -> Optional[str]:
        """The agent's decentralised identifier, or None."""
        return self._did

    @property
    def hardware_fingerprint(self) -> Optional[str]:
        return self._hardware_fingerprint

    @property
    def wallet_address(self) -> Optional[str]:
        """The agent's deterministically derived EVM (Secp256k1) wallet address, or None."""
        return self._evm_address

    def spawn_subagent(self, subagent_id: str) -> "IntegrityClient":
        """
        Frictionless helper to spawn a child subagent instance that inherits
        the parent configuration, DID keys, and credentials, but isolates 
        its own telemetry tracking under a subagent namespace.
        """
        return IntegrityClient(
            agent_id=self.agent_id,
            oracle_url=self.oracle_url,
            batch_size_limit=self.batcher.batch_size_limit,
            flush_interval_sec=self.batcher.flush_interval_sec,
            did=self._did,
            subagent_id=subagent_id,
            enable_full_recording=self.enable_full_recording,
        )

    def _calculate_metrics(self, metadata: dict) -> tuple:
        """
        Calculates heuristic reputation metrics (entropy and grounding) from metadata.
        This allows frictionless telemetry tracking to build the data moat.
        Future updates can replace this with a more sophisticated model.
        """
        # Baseline ideal metrics
        entropy = 0.1
        grounding = 0.95
        
        if not metadata:
            return entropy, grounding
            
        # Extract predefined signals to calculate metrics
        over_sized_count = metadata.get("over_sized_count", 0)
        errors = metadata.get("errors", 0)
        warnings = metadata.get("warnings", 0)
        hallucination_flag = metadata.get("hallucination_flag", False)
        
        # Adjust based on signals
        if over_sized_count > 0:
            entropy += 0.4
            grounding -= 0.2
            
        if errors > 0:
            entropy += (0.2 * errors)
            grounding -= (0.1 * errors)
            
        if warnings > 0:
            entropy += (0.05 * warnings)
            grounding -= (0.02 * warnings)
            
        if hallucination_flag:
            entropy += 0.5
            grounding -= 0.5
            
        # Ensure values stay strictly bounded between 0.0 and 1.0
        return min(max(entropy, 0.0), 1.0), min(max(grounding, 0.0), 1.0)

    def log_model_switch(
        self,
        from_model: str,
        to_model: str,
        from_provider: Optional[str] = None,
        to_provider: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """
        Manually logs a model/provider switch event to the telemetry queue.
        """
        metadata = {
            "event_type": "model_switch",
            "from_model": from_model,
            "to_model": to_model,
            "from_provider": from_provider or "unknown",
            "to_provider": to_provider or "unknown",
            "reason": reason or "dynamic_dispatch",
        }
        self.log_telemetry(metadata=metadata, entropy=0.1, grounding=0.95)

    def log_telemetry(
        self,
        metadata: dict = None,
        entropy: float = None,
        grounding: float = None,
        subagent_id: Optional[str] = None,
    ) -> None:
        """
        Logs a single piece of telemetry.
        Returns immediately without blocking agent inference.
        """
        metadata = metadata or {}
        
        # Check for model switch to avoid recursion and log switch event
        if metadata.get("event_type") != "model_switch":
            model_name = metadata.get("model_name") or metadata.get("model")
            provider_name = metadata.get("provider") or metadata.get("framework")
            if model_name:
                with self._lock:
                    if self.last_model and self.last_model != model_name:
                        self.log_model_switch(
                            from_model=self.last_model,
                            to_model=model_name,
                            from_provider=self.last_provider,
                            to_provider=provider_name,
                            reason="automatic_telemetry_detect"
                        )
                    self.last_model = model_name
                    self.last_provider = provider_name

        # Calculate dynamic inference quality metrics if available in metadata
        import math
        
        # 1. Token logprobs statistics
        logprobs = metadata.get("token_logprobs")
        if logprobs:
            probs = []
            total_logprob = 0.0
            min_prob = 1.0
            for lp in logprobs:
                prob = math.exp(lp)
                probs.append(prob)
                total_logprob += lp
                if prob < min_prob:
                    min_prob = prob
            
            avg_logprob = total_logprob / len(logprobs) if logprobs else 0.0
            mean_conf = math.exp(avg_logprob)
            perplexity = math.exp(-avg_logprob)
            
            metadata["mean_token_confidence"] = round(mean_conf * 100, 2)  # Percentage representation
            metadata["min_token_probability"] = round(min_prob * 100, 2)   # Percentage representation
            metadata["perplexity"] = round(perplexity, 4)
            
            # Map low confidence to higher entropy
            if mean_conf < 0.85:
                entropy = entropy if entropy is not None else min(1.0, (entropy or 0.1) + 0.3)
                grounding = grounding if grounding is not None else max(0.0, (grounding or 0.95) - 0.15)
        
        # 2. Vocabulary diversity (Type-Token Ratio)
        text_out = metadata.get("text_output")
        if text_out:
            words = text_out.lower().split()
            ttr = len(set(words)) / len(words) if words else 1.0
            metadata["vocabulary_diversity"] = round(ttr, 4)
            
        # 3. Structural compliance
        parsing_err = metadata.get("parsing_errors", 0)
        missing_keys = metadata.get("missing_keys", 0)
        if "parsing_errors" in metadata or "missing_keys" in metadata:
            compliance = max(0.0, 1.0 - (parsing_err * 0.5) - (missing_keys * 0.1))
            metadata["structural_compliance"] = round(compliance, 4)

        resolved_subagent_id = subagent_id or self.subagent_id
        if resolved_subagent_id:
            metadata["subagent_id"] = resolved_subagent_id

        # Frictionless metric calculation based on metadata signals
        if entropy is None or grounding is None:
            calc_entropy, calc_grounding = self._calculate_metrics(metadata)
            entropy = entropy if entropy is not None else calc_entropy
            grounding = grounding if grounding is not None else calc_grounding

        payload = {
            "entropy": entropy,
            "grounding": grounding,
            "timestamp": time.time(),
            "metadata": metadata,
            "gpu_hours_used": metadata.get("gpu_hours_used", 0.0),
        }
        self.batcher.add_telemetry(payload)

    def _calculate_edit_distance(self, s1: str, s2: str) -> int:
        """Helper to compute Levenshtein distance between two strings."""
        if len(s1) > len(s2):
            s1, s2 = s2, s1
        distances = range(len(s1) + 1)
        for i2, c2 in enumerate(s2):
            distances_ = [i2+1]
            for i1, c1 in enumerate(s1):
                if c1 == c2:
                    distances_.append(distances[i1])
                else:
                    distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
            distances = distances_
        return distances[-1]

    def log_hitl_action(
        self,
        action_type: str,
        proposed_content: Optional[str] = None,
        final_content: Optional[str] = None,
        reviewer_did: Optional[str] = None,
        review_latency_ms: Optional[float] = None,
        justification: Optional[str] = None,
        extra_metadata: Optional[dict] = None
    ) -> None:
        """
        Logs a human-in-the-loop (HITL) review, approval, or override action.
        """
        edit_distance = None
        if proposed_content is not None and final_content is not None:
            try:
                edit_distance = self._calculate_edit_distance(proposed_content, final_content)
            except Exception:
                pass

        metadata = {
            "event_type": "human_in_the_loop",
            "action_type": action_type,
            "reviewer_did": reviewer_did or "unknown_reviewer",
            "review_latency_ms": review_latency_ms,
            "justification": justification,
            "edit_distance": edit_distance,
        }
        if proposed_content is not None:
            metadata["proposed_length"] = len(proposed_content)
        if final_content is not None:
            metadata["final_length"] = len(final_content)

        if extra_metadata:
            metadata.update(extra_metadata)

        # HITL actions represent a manual override or verification; grounding is set to 1.0 (authoritative)
        self.log_telemetry(
            metadata=metadata,
            entropy=0.0,
            grounding=1.0
        )

    def log_inference(
        self,
        provider: str,
        raw_data: Any,
        latency_ms: Optional[float] = None,
        ttft_ms: Optional[float] = None,
        extra_metadata: Optional[dict] = None,
        entropy: Optional[float] = None,
        grounding: Optional[float] = None,
        subagent_id: Optional[str] = None,
    ) -> None:
        """
        Parses, normalizes, and logs inference-level telemetry from any LLM provider pipeline.
        Extracts prompt/completion tokens, pricing, latency, and hardware environments.
        """
        from .extractor import InferenceMetadataExtractor
        
        metadata = InferenceMetadataExtractor.normalize(
            provider=provider,
            raw_data=raw_data,
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
            enable_full_recording=self.enable_full_recording
        )
        
        if extra_metadata:
            metadata.update(extra_metadata)
            
        self.log_telemetry(
            metadata=metadata,
            entropy=entropy,
            grounding=grounding,
            subagent_id=subagent_id
        )

    # ------------------------------------------------------------------
    # Ownership Claim (MetaMask Association)
    # ------------------------------------------------------------------

    def generate_claim_challenge(self, owner_address: str) -> str:
        """
        Generates a deterministic challenge message for MetaMask signing.
        The human operator signs this message in MetaMask to prove they
        own the wallet and want to claim this agent.

        Parameters
        ----------
        owner_address : str
            The human's MetaMask wallet address (0x...)

        Returns
        -------
        str
            The challenge message to be signed via personal_sign in MetaMask.
        """
        if self._evm_address is None:
            raise RuntimeError("Agent has no derived EVM address. Cannot generate claim challenge.")

        timestamp = int(time.time())
        challenge = (
            f"I, {owner_address.lower()}, claim ownership of agent "
            f"{self._evm_address.lower()} on the Xibalba Integrity Protocol. "
            f"Timestamp: {timestamp}"
        )
        return challenge

    def claim_ownership(
        self,
        owner_address: str,
        signature: str,
        challenge: Optional[str] = None,
    ) -> dict:
        """
        Submits an ownership claim to the Oracle, binding this agent's
        derived wallet to the human operator's MetaMask address.

        Parameters
        ----------
        owner_address : str
            The human's MetaMask wallet address (0x...)
        signature : str
            The EIP-191 personal_sign hex signature from MetaMask
        challenge : str, optional
            The challenge message that was signed. If not provided,
            generates a new one (note: this won't match an already-signed challenge).

        Returns
        -------
        dict
            Response from the Oracle with claim status.

        Raises
        ------
        RuntimeError
            If the agent has no derived EVM address.
        requests.HTTPError
            If the Oracle rejects the claim.
        """
        if self._evm_address is None:
            raise RuntimeError("Agent has no derived EVM address. Cannot claim ownership.")

        if challenge is None:
            challenge = self.generate_claim_challenge(owner_address)

        # Build the Oracle base URL (strip the telemetry path)
        base_url = self.oracle_url.rsplit('/v1/', 1)[0] if '/v1/' in self.oracle_url else self.oracle_url.rstrip('/')
        claim_url = f"{base_url}/v1/agents/claim"

        payload = {
            "agent_wallet": self._evm_address,
            "owner_wallet": owner_address,
            "challenge": challenge,
            "signature": signature,
            "timestamp": int(time.time()),
        }

        response = requests.post(claim_url, json=payload, timeout=10.0)
        response.raise_for_status()
        result = response.json()

        self._owner_address = owner_address
        print(f"[IntegrityClient] Ownership claimed: {self._evm_address} -> {owner_address}")

        return result

    @property
    def owner_address(self) -> Optional[str]:
        """The MetaMask wallet address that owns this agent, if claimed."""
        return getattr(self, '_owner_address', None)

    def get_owner_agents(self, owner_address: Optional[str] = None) -> dict:
        """
        Queries the Oracle for all agents owned by a MetaMask wallet.

        Parameters
        ----------
        owner_address : str, optional
            The owner's MetaMask address. Defaults to this agent's owner.

        Returns
        -------
        dict
            Response with list of agents and aggregate AIS score.
        """
        addr = owner_address or getattr(self, '_owner_address', None)
        if addr is None:
            raise RuntimeError("No owner address specified and agent has no claimed owner.")

        base_url = self.oracle_url.rsplit('/v1/', 1)[0] if '/v1/' in self.oracle_url else self.oracle_url.rstrip('/')
        query_url = f"{base_url}/v1/owner/{addr}/agents"

        response = requests.get(query_url, timeout=10.0)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    def _init_sqlite_cache(self) -> None:
        import sqlite3
        try:
            self._cache_dir = os.path.expanduser("~/.integrity")
            os.makedirs(self._cache_dir, exist_ok=True)
            self._cache_db_path = os.path.join(self._cache_dir, f"offline_moat_{self.agent_id}.db")
            conn = sqlite3.connect(self._cache_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS offline_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    integrity_hash TEXT NOT NULL
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[IntegrityClient] SQLite cache init failed: {e}")

    def _cache_payload_locally(self, payload: dict) -> None:
        import sqlite3
        import hmac
        import hashlib
        try:
            payload_str = json.dumps(payload, sort_keys=True)
            # Row-level integrity hashing using private HMAC seed
            integrity_hash = hmac.new(self._hmac_secret, payload_str.encode(), hashlib.sha256).hexdigest()

            conn = sqlite3.connect(self._cache_db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO offline_telemetry (payload, timestamp, integrity_hash) VALUES (?, ?, ?)",
                (payload_str, time.time(), integrity_hash)
            )
            conn.commit()
            conn.close()
            print(f"[IntegrityClient] Telemetry cached locally inside SQLite.")
        except Exception as ex:
            print(f"[IntegrityClient] Failed to write to SQLite cache: {ex}")

    def _sync_offline_cache(self) -> None:
        import sqlite3
        import hmac
        import hashlib
        try:
            conn = sqlite3.connect(self._cache_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, payload, integrity_hash FROM offline_telemetry ORDER BY id ASC LIMIT 10")
            rows = cursor.fetchall()
            if not rows:
                conn.close()
                return

            print(f"[IntegrityClient] Detected {len(rows)} offline telemetry records. Attempting sync...")
            for row_id, payload_str, stored_hash in rows:
                # 1. Verify offline database row integrity (Devils Advocate fix)
                computed_hash = hmac.new(self._hmac_secret, payload_str.encode(), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(computed_hash, stored_hash):
                    print(f"[WARN] Local SQLite database tampering detected! Discarding tampered row {row_id}.")
                    cursor.execute("DELETE FROM offline_telemetry WHERE id = ?", (row_id,))
                    continue

                payload = json.loads(payload_str)
                response = requests.post(self.oracle_url, json=payload, timeout=5.0)
                response.raise_for_status()
                cursor.execute("DELETE FROM offline_telemetry WHERE id = ?", (row_id,))
            conn.commit()
            conn.close()
            print(f"[IntegrityClient] Successfully synchronized offline cache with Oracle.")
        except Exception:
            pass

    def _background_worker(self) -> None:
        """
        Runs in the background, checking if the batcher should flush.
        If so, generates a ZK proof and transmits it to the Oracle.
        """
        last_sync_time = time.time()
        while self._running:
            if self.batcher.should_flush():
                batch = self.batcher.get_batch_and_clear()
                self._process_and_send(batch)
            
            # Periodically try to sync offline cache (every 10 seconds)
            if time.time() - last_sync_time > 10.0:
                self._sync_offline_cache()
                last_sync_time = time.time()

            time.sleep(0.5)

    def _sign_payload(self, payload_bytes: bytes) -> Optional[str]:
        """Sign raw bytes with the DID keypair; returns hex or None."""
        if self._keypair is None:
            return None
        try:
            sig = self._keypair.sign(payload_bytes)
            return sig.hex()
        except Exception:
            return None

    def _process_and_send(self, batch: list) -> None:
        try:
            # 1. Generate ZK Proof for the batch
            proof_data = self.prover.generate_proof(batch)

            # Calculate batch statistics
            total_entropy = sum(item.get("entropy", 0.0) for item in batch)
            total_grounding = sum(item.get("grounding", 0.0) for item in batch)
            avg_entropy = total_entropy / len(batch) if batch else 0.0
            avg_grounding = total_grounding / len(batch) if batch else 0.0
            total_gpu_hours = sum(item.get("gpu_hours_used", 0.0) for item in batch)

            # Compile a list of all raw metadata in the batch
            raw_metadata_list = [item.get("metadata", {}) for item in batch]

            # 2. Construct base payload
            payload = {
                "agent_id": self.agent_id,
                "zk_proof": proof_data["zk_proof"],
                "nonce": proof_data["nonce"],
                "batch_size": proof_data["batch_size"],
                "avg_entropy": avg_entropy,
                "avg_grounding": avg_grounding,
                "gpu_hours_used": total_gpu_hours,
                "metadata": raw_metadata_list,
            }

            # 3. Attach DID identity + EVM wallet + signature if available
            if self._did is not None:
                payload["agent_did"] = self._did

            if self._hardware_fingerprint is not None:
                payload["hardware_fingerprint"] = self._hardware_fingerprint

            if self._evm_address is not None:
                payload["performer_address"] = self._evm_address

            # Sign ONLY the core deterministic fields to avoid floating point serialization variance
            sig_payload = {
                "agent_id": payload["agent_id"],
                "zk_proof": payload["zk_proof"],
                "nonce": payload["nonce"],
                "batch_size": payload["batch_size"],
            }
            if self._did is not None:
                sig_payload["agent_did"] = self._did
            if self._hardware_fingerprint is not None:
                sig_payload["hardware_fingerprint"] = self._hardware_fingerprint
            if self._evm_address is not None:
                sig_payload["performer_address"] = self._evm_address

            serialized_payload = json.dumps(sig_payload, sort_keys=True, separators=(",", ":"))
            print(f"[DEBUG SDK] CANONICAL JSON: {serialized_payload}")
            sig = self._sign_payload(serialized_payload.encode())
            if sig is not None:
                payload["signature"] = sig

            # 4. Transmit to Oracle via HTTP ingestion
            response = requests.post(
                self.oracle_url, json=payload, timeout=5.0
            )
            response.raise_for_status()
        except Exception as e:
            print(f"[IntegrityClient] Transmission failed, caching locally: {e}")
            self._cache_payload_locally(payload)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown(self):
        """Clean shutdown ensuring all remaining batches are flushed."""
        self._running = False
        self._worker_thread.join(timeout=2.0)
        # Drain any remaining items (may require multiple flushes)
        while True:
            batch = self.batcher.get_batch_and_clear()
            if not batch:
                break
            self._process_and_send(batch)

