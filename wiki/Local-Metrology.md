# Cognitive Local Metrology Heuristics 🧠

A core design principle of the Integrity Protocol is **client-side metrics evaluation**. The SDK must evaluate and calculate cognitive telemetry parameters locally on raw prompt/completion arrays before they are signed and transmitted, keeping the off-chain oracle server fully stateless and zero-trust.

---

## 1. Token Logprobability Entropy

Perplexity and token distribution entropy are critical metrics for tracking model cognitive stability, repeating loops, or sudden perplexity spikes (indicating potential model hijacking or jailbreaks).

- **The Calculation**:
  For a completion containing $N$ generated tokens, the local metrology parser extracts the logprobabilities $p(t_i)$ of each generated token:
  $$\text{Entropy} = -\frac{1}{N} \sum_{i=1}^{N} p(t_i) \log p(t_i)$$
- **Repetitive Loops**: If an agent gets stuck in a repetitive loop (e.g. repeating the same sentence), token entropy collapses to nearly zero.
- **Jailbreak Perplexity**: A sudden, extreme spike in logprobability entropy suggests that the model is processing unexpected structures, indicating a high-risk security breach.

---

## 2. Sliding-Window Grounding & Context Adherence

To mathematically ensure that an agent is not hallucinating or outputting fabrications outside its retrieved knowledge bases (RAG context), the SDK runs a local sliding-window context adherence parser:

1. **RAG Extraction**: Intercepts the retrieved documents injected into the system prompt.
2. **N-Gram Overlap**: Breaks both the RAG context and the generated completion into $N$-grams (default: $N=3$).
3. **Alignment Score**: Calculates the proportion of completion $N$-grams that directly exist inside the retrieved RAG context:
   $$\text{Grounding Index} = \frac{|N\text{-grams}_{\text{completion}} \cap N\text{-grams}_{\text{RAG}}|}{|N\text{-grams}_{\text{completion}}|}$$
4. If the grounding index falls below standard thresholds (e.g., $< 0.70$), the SDK marks the batch as containing high perplexity or potential hallucinations.

---

## 3. Heuristic Task Completion (Heuristic Loop)

The SDK implements automated heuristics to verify successful execution bounds:
- **Git Commit Check**: Hooks terminal harnesses to verify code commit success.
- **HTTP Return Codes**: Parses agent tool-use HTTP return statuses.
- **User-in-the-Loop Hooks**: Intercepts user feedback inputs to evaluate reputation adjustments.

By processing these dimensions locally, the agent self-documents its **Agent Integrity Score (AIS)**, which is then cryptographically sealed via Aztec Noir ZK-proofs and signed in transit!
