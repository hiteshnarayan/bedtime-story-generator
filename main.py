import os
import sys
import json
import anthropic

from prompts import STORYTELLER_SYSTEM, PLANNER_SYSTEM, CATEGORY_STYLE, JUDGE_SYSTEM

"""
Before submitting the assignment, describe here in a few sentences what you would have built next if you spent 2 more hours on this project:

"""
client  = anthropic.Anthropic()
MODEL = "claude-haiku-5-5"

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
    """ Categorise then Outlines the story arc """
    plan = call_for_json(f"Parent's Request: {request}", PLANNER_SYSTEM)
    if plan.get("category") not in CATEGORY_STYLE:
        plan["category"] = "friendship" # default
    return plan

def write_story(request: str, plan:dict) -> str:
    """  Generators the story """
    style = CATEGORY_STYLE[plan["category"]]
    prompt = (f"Parent's request: {request}\n\n"f"Story plan:\n{json.dumps(plan, indent=2)}\n\n"f"Style for this kind of story: {style}")
    return call_model(prompt=prompt, max_tokens=2000, system=STORYTELLER_SYSTEM)

def judge_story(request: str, story: str) -> dict:
    """  Score the story on 6 bedtime criteria and suggest fixes """
    return call_for_json(f"Parent's request: {request}\n\nStory:\n{story}", JUDGE_SYSTEM, max_tokens=4000)



def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Please set the ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)

    user_input = input("What kind of story do you want to hear? (press Enter for an example)?").strip()
    request = user_input or example_requests

    print("Planning the story:")
    plan = plan_story(request)
    print(f"Category: {plan['category']}\nTitle: {plan.get('title', '')}")

    print("\nWriting:")
    story = write_story(request,plan)
    print("\n"+story)

    print("\nJudging:")
    judgement = judge_story(request, story)
    print(json.dumps(judgement, indent=2))


if __name__ == "__main__":
    main()