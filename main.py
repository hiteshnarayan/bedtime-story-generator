import os
import sys

import anthropic

from prompts import STORYTELLER_SYSTEM

"""
Before submitting the assignment, describe here in a few sentences what you would have built next if you spent 2 more hours on this project:

"""
client  = anthropic.Anthropic()
def call_model(prompt: str, max_tokens=3000, system: str |None = None) -> str:
    kwargs = {"system": system} if system else {}
    res = client.messages.create(
        model = "claude-haiku-5-5",
        max_tokens = max_tokens,
        messages = [{"role": "user", "content": prompt}],
        **kwargs,
    )
    return  "".join(b.text  for b in res.content if b.type == "text")

example_requests = "A story about a girl named Alice and her best friend Bob, who happens to be a cat."


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Please set the ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)
    user_input = input("What kind of story do you want to hear? ")
    response = call_model(user_input, system=STORYTELLER_SYSTEM)
    print(response)


if __name__ == "__main__":
    main()