"""
Script to generate a summary of JIRA tickets for a given filter.

You will need a JWT for your Duolingo account and a JIRA API token:
https://id.atlassian.com/manage-profile/security/api-tokens

How to run
$ export DUOLINGO_JWT=[your JWT]
$ export JIRA_API_TOKEN=[your JIRA API token]
$ python analyze_jira_tickets.py [name of the filter] [your duolingo email address minus @duolingo.com]
"""
import json
import os
from typing import Any, Dict, List, Optional

import requests

# tutors-backend API URLS
TUTORS_BASE_URL = "https://duolingo-tutors-prod.duolingo.com"

MODEL_NAME = "text-alpha-002-duolingo"
_PLAIN_FMT = "{prompt}"

# # Set up. We can use the same sessions throughout
tutors_session = requests.Session()
tutors_session.headers = {
    "Authorization": "Bearer {}".format(os.environ["DUOLINGO_JWT"]),
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def build_prompt(file: str) -> str:
    """Build the prompt for the tutors-backend API."""
    with open(file, "r") as file:
        fileContent = file.read()
    requestString = "Add Comments to this code: " + fileContent
    return requestString


def _create_completion_request_data(
    prompt: str,
    model: str,
    stop_tokens: Optional[List[str]],
    max_tokens: int,
    temperature: float,
    top_p: float,
    logit_bias: Dict[str, int] = None,
) -> Dict[str, Any]:
    return {
        "model": model,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "prompt": prompt,
        "stop": stop_tokens,
        "logit_bias": logit_bias or {},
    }


def get_completion_single(
    prompt: str,
    stop_tokens: Optional[List[str]],
    max_tokens: int = 128,
    temperature: float = 1.0,
    top_p: float = 0.8,
    model=MODEL_NAME,
    logit_bias: Dict[str, int] = None,
    fmt=_PLAIN_FMT,
) -> str:
    tutors_endpoint = f"{TUTORS_BASE_URL}/2017-06-30/tutors/ai/completion_request"

    prompt_formatted = fmt.format(prompt=prompt)
    data = json.dumps(
        _create_completion_request_data(
            prompt_formatted, model, stop_tokens, max_tokens, temperature, top_p, logit_bias
        )
    )

    response = tutors_session.post(tutors_endpoint, data=data)
    response.raise_for_status()

    # TODO: Handle failure
    return response.content.decode("utf-8")
