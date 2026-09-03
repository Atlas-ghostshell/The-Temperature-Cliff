# The Temperature Cliff

> A lab built to test LLM sampling behavior ended up catching Anthropic's API mid-transition — the exact model generation where `temperature` stops working and `effort` takes its place.

## Overview

Week 3 of the AI Security Engineering Roadmap moves from general neural network theory into the specific architecture behind every LLM: tokenization, embeddings, self-attention, context windows, temperature and sampling, and the four distinct levers — pretraining, fine-tuning, prompting, RAG — that actually shape model behavior. The hands-on lab was designed to make one specific piece of that theory concrete: run identical prompts at different temperatures against a real model, and watch the output distribution sharpen and flatten exactly as the math predicts.

That's not quite what happened. The lab plan assumed `temperature` was a stable, ordinary parameter — because it always has been, since the Messages API existed. Three infrastructure detours and one broken script later, it turned out the parameter itself was mid-retirement, and the specific model available for testing happened to sit on the last side of that line before Anthropic started hard-rejecting it entirely.

## What Was Supposed to Happen vs. What Actually Happened

```
PLANNED PATH
  platform.claude.com --> API key --> run script --> collect results
                                            |
                                            v
ACTUAL PATH
  platform.claude.com --> billing wall (KRA PIN required, Kenya tax compliance)
       |
       v
  pivot: AWS Bedrock (existing AWS account, no separate verification)
       |
       v
  IAM wall (GetSessionToken rejected -- Shepherd's session creds already temporary)
       |
       v
  scoped throwaway IAM user, created and destroyed per run
       |
       v
  script wall: TypeError -- temperature not a valid parameter in anthropic SDK v1.3.0
       |
       v
  investigated: temperature removed from typed SDK interface entirely, ALL models,
  replaced by output_config={"effort": ...} -- NOT an equivalent control
       |
       v
  investigated further: temperature hard-rejected (400 error) on Opus 4.7+ / Sonnet 5,
  but still genuinely functional on Opus 4.6 -- confirmed via extra_body injection
       |
       v
  ran the ORIGINAL experiment for real, on the exact model generation
  where it still works, three independent times
```

## Experiment 1 — BPE Tokenization, Built From Scratch

Rather than depend on a hosted tokenizer library (blocked by this environment's network allowlist), the actual Byte-Pair Encoding merge algorithm was implemented directly and trained on a small toy corpus. Three results worth stating precisely:

- **`lowest`** (frequency 6 in training) collapsed into a single merged token — frequent sequences compress, exactly as theory predicts.
- **`newest`** was never in the training data at all, and still tokenized cleanly by reusing subword pieces learned from `new` and `newer` — the graceful-fallback property, demonstrated rather than asserted.
- **`wider`** *was* in the training data (frequency 3) and still didn't fully merge after 8 merge steps — proof that vocabulary size is a competitive budget, not a guarantee tied to frequency alone.

## The Discovery — Temperature Is Being Retired, Live

Attempting to run the original temperature-sweep script threw:

```
TypeError: Messages.create() got an unexpected keyword argument 'temperature'
```

Direct inspection of the installed SDK (`anthropic==1.3.0`, confirmed as the current latest release, not a stale version) confirmed `temperature`, `top_p`, and `top_k` are structurally absent from `Messages.create()`'s signature — not model-conditional, removed for every model called through that client. In their place: `output_config={"effort": "low"|"medium"|"high"|"xhigh"|"max"}` — a reasoning-depth and compute-budget control, not a sampling-randomness control. The two are not interchangeable.

Further investigation found this is a real, staged rollout, not a bug: Claude Opus 4.7/4.8 and Sonnet 5 return an explicit `400 invalid_request_error: temperature is deprecated for this model` the moment the field is present in a request — confirmed independently across several unrelated projects hitting the live API, including one team's own before/after verification against production. **Opus 4.6 — one generation earlier — still reads and genuinely acts on the field.** Sending it via `extra_body` (which injects a raw key into the request body, bypassing the SDK's typed interface entirely) still produces real, working sampling temperature on that specific model.

The experiment below is therefore not a workaround dressed up as a result — it's a legitimate confirmation of Week 3's core theory, run on the exact model generation sitting at the boundary of the mechanism being retired.

## Experiment 2 — Temperature / Sampling Divergence (3 Independent Runs)

Fixed prompt, three temperatures, three runs each, repeated as three fully separate script executions.

| Run | T=0.0 unique | T=0.7 unique | T=1.0 unique |
|---|---|---|---|
| 1 | 1 | 2 | 2 |
| 2 | 1 | 2 | 3 |
| 3 | 2 | 2 | 2 |
| **Mean** | **1.33** | **2.0** | **2.33** |

The averaged trend matches theory: divergence rises with temperature. Two individual results are worth stating precisely rather than smoothing over:

- **Run 3 at T=0.0 didn't fully converge** — 2 unique outputs, not 1. Temperature 0 sharpens the distribution toward greedy but doesn't guarantee bit-identical output across separate inference passes; this is a legitimate observation about real-world determinism limits, not measurement error.
- **Run 3 at T=1.0 included a full sentence restructure, not a word swap** — divergence at higher temperature ranged from single-word substitution up to complete rephrasing, not uniformly mild variation.

One counterintuitive result worth naming directly: in Run 2 at T=1.0, one of the three outputs landed exactly on the deterministic T=0.0 answer, purely by chance. Temperature 1 means sampling honestly from the real distribution — not avoiding the most likely token. If the top choice still carries substantial probability mass, which a narrow one-sentence factual prompt guarantees, it can and will still come up.

## Experiment 3 — Prompt Structure Sensitivity

Same core question — "is it safe to store API keys in a public GitHub repo?" — asked three different ways, temperature fixed low (0.2) across all three so structure was the only variable in motion. The expected result held across all three independent runs: wording varied, the substantive verdict never did.

The unplanned finding is the more interesting one. The `role_framed` variant (a system prompt establishing a strict security-reviewer persona) produced the **identical opening two sentences, word-for-word, in all three independent runs** — while the bare, unframed question visibly restructured its formatting and content every time. Locking down context — a persona, or a rigid three-field output format — measurably narrowed the model's effective output distribution at the exact same temperature setting. That's the same sharpening effect temperature produces, achieved here entirely through prompt structure instead of the sampling parameter. Experiment 3 wasn't designed to test that, and demonstrated it anyway.

## Key Conceptual Anchors

- A token is an opaque integer with no built-in character-level visibility — tokenization failures (letter-counting, arithmetic) follow directly from this, not from a reasoning defect.
- Embeddings are learned weights, not computed transformations of a token ID — trained by the same backpropagation mechanism as every other weight in the network.
- Self-attention replaces a static, context-blind embedding with a context-aware vector via a softmax-weighted blend of every other token's value — the mechanism that makes "bank" mean different things in different sentences.
- Attention cost scales with the square of sequence length — the direct cause of context window limits, not an arbitrary product decision.
- Temperature reshapes the token probability distribution before sampling; low temperature sharpens toward greedy, high temperature flattens toward random.
- Only pretraining and fine-tuning change model weights. Prompting and RAG both operate on a frozen model, changing only the input — a hard fork in kind, not a spectrum.
- APIs evolve. A parameter this roadmap's own theory is built around is already being phased out in production, on a timeline that started before this lab was even designed.

## Part of the AI Security Engineering Roadmap

| Week | Focus | Status |
|---|---|---|
| 1 | What AI/ML Actually Is | Complete |
| 2 | How Neural Networks Work | Complete |
| **3** | **How LLMs Specifically Work** | **Complete** |
| 4 | The Modern AI Application Stack | Coming soon |
| 5–9 | AI Security Core (OWASP LLM Top 10, prompt injection offense/defense, adversarial ML, agentic AI security, MITRE ATLAS) | Upcoming |
| 10–12 | Securing AI in the Cloud (Bedrock, SageMaker, AI supply chain) | Upcoming |
| 13–14 | Capstone: Black-Box Red Team Assessment, Portfolio Consolidation | Upcoming |

*Companion track to the AWS Cloud Security Engineering Roadmap. Full experiment logs and lab scripts in this repository.*
