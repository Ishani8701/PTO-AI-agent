"""Faithfulness judge — G-Eval style (structured rubric, judge reasons
before scoring, structured output). Uses Azure OpenAI specifically because
the agent under test runs on Anthropic — cross-model judging avoids a model
grading its own kind of output (see app/config.py's long-standing comment:
Azure OpenAI was kept around for exactly this reason).

Judge weaknesses (documented per EVAL_PLAN.md's own requirement):
- A single GPT-4o-mini call, not an ensemble — some score variance run to
  run is expected and not itself a signal of a real regression.
- The judge only sees tool RESULTS, not the retrieval ranking process — a
  correct-but-suboptimal retrieval could still score high here if the
  chunks it did get happen to support the response.
- Only the FINAL reply in a multi-turn case is scored (the rest of the
  transcript is given as context, not scored itself) — a hallucination in
  an earlier turn that never resurfaces in the final reply would not be
  caught by this judge. Deliberate scope decision: for this project's
  actual multi-turn shapes (clarify -> confirm -> submit), the claims worth
  checking concentrate at the points where the agent first states
  something back or wraps up, not in a bare "yes, go ahead" middle turn.
Future improvement: sample multiple judge calls per case and average, to
reduce single-call variance; score every turn (not just the final one) and
take the minimum rather than an average, to catch intermediate hallucinations
without diluting a real failure the way averaging would.
"""

from __future__ import annotations

import json

from openai import AzureOpenAI

from app import config

_SYSTEM_PROMPT = """\
# Role
You are a strict evaluator judging whether an AI assistant's response is \
FAITHFUL to the real data it had access to — grounded, not hallucinated.

# Task
You'll see the full conversation (every user turn and every assistant \
reply) and the actual tool/retrieval results the assistant had access to. \
Score how faithful the assistant's FINAL reply specifically is to that \
data — use the earlier turns only as context for what was actually asked, \
confirmed, or requested (e.g. checking that a "here's your request" \
restatement genuinely matches what was asked several turns earlier).

# Scoring scale (1-5)
5 — Every factual claim (numbers, dates, statuses, policy statements) is \
directly supported by the tool results. No invention.
3 — Mostly faithful, but at least one claim isn't clearly supported by the \
data provided, or includes a minor unsupported elaboration.
1 — Substantially fabricated — confidently states things (numbers, \
statuses, policy claims) with no grounding at all in the provided data.
Use 2 or 4 for cases that fall clearly between two of these anchors.

Why this scale: concrete behavioral anchors (rather than an open-ended \
1-100) make scores more consistent across runs and more interpretable when \
reading a report later.

# Format
Reason step by step first about which specific claims in the response are \
or aren't supported by the provided data, THEN call the `score` tool with \
your final answer. Do not skip the reasoning step.
"""

_SCORE_TOOL = {
    "type": "function",
    "function": {
        "name": "score",
        "description": "Submit the faithfulness score and reasoning.",
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Step-by-step: which claims are grounded, which aren't, and why.",
                },
                "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
            },
            "required": ["reasoning", "score"],
        },
    },
}


def judge_faithfulness(transcript: list[dict], trace: list[dict]) -> dict:
    """transcript: [{"user": "...", "assistant": "..."}, ...] in order —
    the full conversation. Only the LAST entry's "assistant" text is being
    scored; everything before it is context (see module docstring).
    """
    client = AzureOpenAI(
        api_key=config.AZURE_API_KEY,
        azure_endpoint=config.AZURE_ENDPOINT,
        api_version=config.AZURE_API_VERSION,
    )
    context = json.dumps(
        [{"tool": t["tool"], "result": t["result"]} for t in trace], default=str, indent=2
    )
    convo = "\n\n".join(
        f"Turn {i + 1} — USER: {t['user']}\nTurn {i + 1} — ASSISTANT: {t['assistant']}"
        for i, t in enumerate(transcript)
    )
    user_prompt = (
        f"FULL CONVERSATION:\n{convo}\n\n"
        f"Score the FINAL assistant reply above (Turn {len(transcript)}).\n\n"
        f"ACTUAL DATA THE ASSISTANT HAD ACCESS TO (tool call results):\n{context}"
    )

    resp = client.chat.completions.create(
        model=config.AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        tools=[_SCORE_TOOL],
        tool_choice={"type": "function", "function": {"name": "score"}},
    )
    args = json.loads(resp.choices[0].message.tool_calls[0].function.arguments)
    return {"score": args["score"], "reasoning": args["reasoning"]}
