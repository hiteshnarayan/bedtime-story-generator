import json
import os
import sys

import anthropic

from prompts import STORYTELLER_SYSTEM, PLANNER_SYSTEM, CATEGORY_STYLE, JUDGE_SYSTEM

"""
Before submitting the assignment, describe here in a few sentences what you would have built next if you spent 2 more hours on this project:

"""
client  = anthropic.Anthropic()
MODEL = "claude-haiku-5-5"
PASS_SCORE = 8  # every criterion must reach this to pass
CRITERIA = ("age_fit", "safety", "follows_request", "story_arc", "engagement", "bedtime_calm")

def call_model(prompt: str, max_tokens=8000, system: str |None = None) -> str:
    kwargs = {"system": system} if system else {}
    res = client.messages.create(
        model = MODEL,
        max_tokens = max_tokens,
        messages = [{"role": "user", "content": prompt}],
        **kwargs,
    )
    if res.stop_reason == "max_tokens":
        print(f"WARNING: output cut off at max_tokens={max_tokens}", file=sys.stderr)
    return  "".join(b.text  for b in res.content if b.type == "text").strip()

example_requests = "A story about a girl named Alice and her best friend Bob, who happens to be a cat."


def parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                return None
    return None

def call_for_json(prompt: str, system: str, max_tokens: int = 1000) -> dict:
    data = parse_json(call_model(prompt, max_tokens=max_tokens, system=system))

    if data is None: # forcing it return the required JSON format
        data = parse_json(call_model(prompt + "\n\nReturn ONLY valid JSON.", max_tokens=max_tokens, system=system))
    if data is None: # if parse fails
        raise ValueError("Model did not return valid JSON after a retry.")
    return data

def plan_story(request: str) -> dict:
    """Categorize the request and outline a 5-beat arc."""
    plan = call_for_json(f"Parent's Request: {request}", PLANNER_SYSTEM, max_tokens=4000)
    if plan.get("category") not in CATEGORY_STYLE:
        plan["category"] = "friendship" # default
    return plan

def write_story(request: str, plan: dict, judgement: dict | None = None, draft: str | None = None) -> str:
    """Write the story from the plan, or revise the draft using the judge's fixes."""
    style = CATEGORY_STYLE[plan["category"]]
    prompt = (
        f"Parent's request: {request}\n\n"
        f"Story plan:\n{json.dumps(plan, indent=2)}\n\n"
        f"Style for this kind of story: {style}"
    )
    if judgement and draft:
        prompt += (
            f"\n\nCurrent draft:\n{draft}\n\n"
            "Revise this draft. Keep what already works and only change what the judge asked to fix.\n"
            f"Issues:\n{json.dumps(judgement.get('issues', []), indent=2)}\n"
            f"Fixes:\n{json.dumps(judgement.get('fixes', []), indent=2)}"
        )
    return call_model(prompt=prompt, max_tokens=8000, system=STORYTELLER_SYSTEM)

def judge_story(request: str, story: str) -> dict:
    """Score the story on 6 bedtime criteria and suggest fixes."""
    return call_for_json(f"Parent's request: {request}\n\nStory:\n{story}", JUDGE_SYSTEM, max_tokens=4000)

def passes(judgement: dict) -> bool:
    """Story passes only if every criterion reaches PASS_SCORE, not just the avg."""
    scores = judgement.get("scores", {})
    try:
        return all(int(scores[c]) >= PASS_SCORE for c in CRITERIA)
    except (KeyError, TypeError, ValueError):  # missing or non-numeric score counts as a fail
        return False

def show_scores(label: str, judgement: dict) -> None:
    print(f"\n[Judge] {label}")
    scores = judgement.get("scores", {})
    for name in CRITERIA:
        print(f"  {name:<16} {scores.get(name, '-')}")
    if not passes(judgement):
        print("  Fixes:")
        for fix in judgement.get("fixes", []):
            print(f"   - {fix}")


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Please set the ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)

    user_input = input("What kind of story do you want to hear? (press Enter for an example) ").strip()
    request = user_input or example_requests
    if not user_input:
        print(f"Using example: {example_requests}")

    try:
        print("\nPlanning the story...")
        plan = plan_story(request)
        print(f"Category: {plan['category']}\nTitle: {plan.get('title', '')}")

        print("\nWriting...")
        story = write_story(request, plan)
        print("\n" + story)

        print("\nJudging...")
        judgement = judge_story(request, story)
        show_scores("First draft", judgement)

        if not passes(judgement):
            print("\nRevising with the judge's notes...")
            story = write_story(request, plan, judgement, draft=story)
            print("\n" + story)
            judgement = judge_story(request, story)
            show_scores("Revised draft", judgement)

        print("  Result:", "PASS" if passes(judgement) else "best attempt after revision")
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(130)
    except (anthropic.APIError, ValueError) as e:
        print(f"\nCould not finish: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()