"""
Week 3 Lab — Experiments 2 & 3
Run this yourself: pip install "anthropic[bedrock]" --break-system-packages
                    export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
                    python3 exp2_3_temperature_and_prompt_structure.py

Writes a timestamped markdown log to ./week3_experiment_log.md as it runs --
that file IS your lab deliverable draft, ready to fold into the README.
"""
from anthropic import AnthropicBedrock
from datetime import datetime, timezone

# Reads AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN from env,
# or falls back to your default AWS credential chain (~/.aws/credentials, profile, etc.)
client = AnthropicBedrock(aws_region="us-east-1")

# Opus 4.6 requires an inference-profile ID, NOT the bare model ID — confirm
# the exact prefix for YOUR account/region first:
#   aws bedrock list-inference-profiles --region us-east-1 \
#     --query "inferenceProfileSummaries[?contains(inferenceProfileId, 'opus-4-6')].inferenceProfileId"
# "us." below is the best guess pending that check — swap to "global." if this
# still throws "provided model identifier is invalid".
MODEL = "us.anthropic.claude-opus-4-6-v1"
LOG_PATH = "week3_experiment_log.md"

log_lines = [f"# Week 3 Lab — Experiment Log", f"Run: {datetime.now(timezone.utc).isoformat()}Z\n"]

def call(prompt, temperature, system=None, max_tokens=200):
    # temperature/top_p/top_k were removed from the typed SDK interface entirely
    # in anthropic 1.3.0 (confirmed: not model-specific, structurally absent from
    # Messages.create()'s signature). extra_body injects it into the raw request
    # body directly, bypassing the SDK's type checking -- this makes "does the API
    # still honor it at all" an empirical question the experiment now answers.
    kwargs = dict(model=MODEL, max_tokens=max_tokens,
                  messages=[{"role": "user", "content": prompt}],
                  extra_body={"temperature": temperature})
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    return resp.content[0].text.strip()

# ---------------------------------------------------------------
# EXPERIMENT 2 — Temperature / sampling divergence
# Same exact prompt, same temperature settings run multiple times each.
# Prediction from theory: temperature 0 should converge on near-identical
# outputs every run (sharp distribution). Temperature 1 should visibly
# diverge run to run (flatter distribution, real sampling variance).
# ---------------------------------------------------------------
prompt_2 = "In exactly one sentence, describe what a firewall does."
temperatures = [0.0, 0.7, 1.0]
runs_per_temp = 3

log_lines.append("## Experiment 2: Temperature / Sampling Divergence")
log_lines.append("**Note:** `temperature` was found to be fully removed from the typed "
                  "`anthropic` SDK interface as of v1.3.0 (confirmed via signature inspection, "
                  "not model-specific) -- replaced by an `effort` reasoning-budget control, which "
                  "is NOT equivalent to sampling temperature. This experiment sends `temperature` "
                  "via `extra_body` to test empirically whether the underlying API still honors it "
                  "despite the SDK dropping it from its typed interface.\n")
log_lines.append(f"Prompt (fixed): `{prompt_2}`\n")

for t in temperatures:
    log_lines.append(f"### Temperature = {t}")
    outputs = []
    for i in range(runs_per_temp):
        out = call(prompt_2, temperature=t)
        outputs.append(out)
        log_lines.append(f"- Run {i+1}: {out}")
    unique = len(set(outputs))
    log_lines.append(f"\n**Unique outputs out of {runs_per_temp} runs: {unique}**\n")

# ---------------------------------------------------------------
# EXPERIMENT 3 — Prompt structure sensitivity
# Same underlying question, three different framings, temperature fixed
# low (0.2) so we're isolating the effect of PROMPT STRUCTURE, not sampling
# randomness, as the variable under test.
# ---------------------------------------------------------------
log_lines.append("## Experiment 3: Prompt Structure Sensitivity")
FIXED_TEMP = 0.2

framings = {
    "bare_question": {
        "system": None,
        "prompt": "Is it safe to store API keys in a public GitHub repo?",
    },
    "role_framed": {
        "system": "You are a strict senior security engineer doing a code review. "
                   "You do not soften bad practices.",
        "prompt": "Is it safe to store API keys in a public GitHub repo?",
    },
    "structured_reasoning": {
        "system": None,
        "prompt": "Is it safe to store API keys in a public GitHub repo? "
                   "Answer in this exact format:\nVerdict: <one word>\nRisk: <one sentence>\nFix: <one sentence>",
    },
}

for name, cfg in framings.items():
    out = call(cfg["prompt"], temperature=FIXED_TEMP, system=cfg["system"])
    log_lines.append(f"### Framing: {name}")
    if cfg["system"]:
        log_lines.append(f"System prompt: `{cfg['system']}`")
    log_lines.append(f"User prompt: `{cfg['prompt']}`\n")
    log_lines.append(f"Output:\n```\n{out}\n```\n")

with open(LOG_PATH, "w") as f:
    f.write("\n".join(log_lines))

print(f"Done. Full log written to {LOG_PATH}")
print("Read it, then note in your own words: did temperature 0 actually converge?")
print("Did the SAME weights produce meaningfully different verdicts across framings?")
