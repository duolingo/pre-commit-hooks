from get_completions import build_prompt, get_completion_single

completion = get_completion_single(build_prompt("./testing.py"), [";"]).strip()
print(completion.strip())
