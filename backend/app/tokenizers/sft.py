"""Format a source-backed question for assistant-only causal supervision."""

import json
from typing import Annotated

from pydantic import Field, StrictInt, StrictStr

from ..datasets.storage import DatasetError
from ..schemas import Model
from .schemas import SPECIAL_TOKENS

TEMPLATE_VERSION = "source-qa-v1"
Text = Annotated[StrictStr, Field(min_length=1, max_length=16_384)]


class SftPreview(Model):
    question: Text
    excerpt: Text
    answer: Text
    contextLength: Annotated[StrictInt, Field(ge=8, le=1024)]


def format_example(tokenizer, example: SftPreview):
    if not all(text.strip() for text in (example.question, example.excerpt, example.answer)):
        raise DatasetError("Question, source excerpt and answer must contain text.")

    # Quote data so an embedded newline cannot introduce another template field.
    question = json.dumps(example.question, ensure_ascii=False)
    excerpt = json.dumps(example.excerpt, ensure_ascii=False)
    prompt = f"Source: {excerpt}\nQuestion: {question}\nAnswer:\n"
    try:
        prompt.encode("utf-8")
        example.answer.encode("utf-8")
    except UnicodeEncodeError:
        raise DatasetError("The example must contain valid Unicode.") from None

    prompt_ids = tokenizer.encode(prompt, add_special_tokens=False).ids
    answer_ids = tokenizer.encode(example.answer, add_special_tokens=False).ids
    if not answer_ids or any(index in SPECIAL_TOKENS.values() for index in (*prompt_ids, *answer_ids)):
        raise DatasetError("The tokenizer must encode the example without reserved token IDs.")

    prefix = [SPECIAL_TOKENS["[BOS]"], *prompt_ids]
    targets = [*answer_ids, SPECIAL_TOKENS["[EOS]"]]
    real = len(prefix) + len(targets)
    padding = example.contextLength - real
    if padding < 0:
        raise DatasetError(f"The complete example needs {real} tokens. Shorten it or increase context length.")

    return {
        "templateVersion": TEMPLATE_VERSION,
        "inputIds": prefix + targets + [SPECIAL_TOKENS["[PAD]"]] * padding,
        "attentionMask": [1] * real + [0] * padding,
        "labels": [-100] * len(prefix) + targets + [-100] * padding,
        "promptTokens": len(prefix),
        "supervisedTokens": len(targets),
    }
