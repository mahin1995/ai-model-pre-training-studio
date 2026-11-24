"""Prompt contract shared by the API and the isolated training runtime."""

import json

TEMPLATE_VERSION = "source-qa-v1"


def format_prompt(question, excerpt):
    quoted_question = json.dumps(question, ensure_ascii=False)
    quoted_excerpt = json.dumps(excerpt, ensure_ascii=False)
    return f"Source: {quoted_excerpt}\nQuestion: {quoted_question}\nAnswer:\n"
