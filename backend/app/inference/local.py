"""Load a checkpoint from an extracted Studio training bundle and generate locally."""

import argparse
import json
from pathlib import Path

import torch
from tokenizers import Tokenizer

from ..tokenizers.sft_template import TEMPLATE_VERSION, format_prompt
from ..training.data import digest
from .core import generate, load_model


def verify_file(path, expected):
    if path.stat().st_size != expected["sizeBytes"] or digest(path) != expected["sha256"]:
        raise ValueError(f"Artifact checksum does not match for {path.name}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Extracted training bundle directory")
    parser.add_argument("--step", type=int, help="Checkpoint step, defaulting to the final step")
    parser.add_argument("--prompt", required=True, help="Completion prompt or question")
    parser.add_argument("--excerpt", help="Source excerpt for SFT checkpoints")
    parser.add_argument("--max-new-tokens", type=int, default=32, choices=(8, 16, 32, 64, 128))
    args = parser.parse_args()

    try:
        manifest = json.loads((args.bundle / "manifest.json").read_text())
        configuration = manifest["configuration"]
        release_path = args.bundle / "release.json"
        released_step = manifest["report"]["completedSteps"]
        if release_path.is_file():
            release = json.loads(release_path.read_text())
            for name, sha256 in release["sha256"].items():
                path = (args.bundle / name).resolve()
                if not path.is_relative_to(args.bundle.resolve()) or digest(path) != sha256:
                    raise ValueError(f"Release artifact checksum does not match for {name}.")
            released_step = release["step"]
        step = args.step if args.step is not None else released_step
        checkpoint = args.bundle / "checkpoints" / f"step-{step:06d}"
        descriptor = json.loads((checkpoint / "checkpoint.json").read_text())
        for filename in ("model.safetensors", "config.json", "generation_config.json"):
            if filename in descriptor["files"] or filename != "generation_config.json":
                verify_file(checkpoint / filename, descriptor["files"][filename])
            elif (checkpoint / filename).exists():
                raise ValueError("Unexpected generation configuration in the checkpoint.")
        from ..training.core import config_hash

        if descriptor["step"] != step or descriptor["configHash"] != config_hash(configuration):
            raise ValueError("The checkpoint does not match the training bundle.")
        if descriptor["sourceIdentity"] != manifest["source"]["sourceIdentity"]:
            raise ValueError("The checkpoint source does not match the training bundle.")

        tokenizer_path = args.bundle / "tokenizer.json"
        verify_file(tokenizer_path, manifest["artifacts"]["tokenizer"])
        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        tokenizer.encode_special_tokens = True
        tokenizer.no_padding()
        tokenizer.no_truncation()
        if tokenizer.get_vocab_size() != configuration["vocabSize"] or any(
            tokenizer.token_to_id(token) != index for token, index in configuration["specialIds"].items()
        ):
            raise ValueError("The tokenizer does not match the training configuration.")

        prompt = args.prompt
        if configuration.get("objective") == "sft":
            if configuration.get("templateVersion") != TEMPLATE_VERSION:
                raise ValueError("Unsupported SFT prompt template.")
            if not args.excerpt or not args.excerpt.strip() or not prompt.strip():
                raise ValueError("SFT requires both a question and a source excerpt.")
            prompt = format_prompt(prompt, args.excerpt)
        elif args.excerpt is not None:
            raise ValueError("A separate excerpt requires an SFT checkpoint.")
        torch.set_num_threads(2)
        result = generate(load_model(checkpoint, configuration), tokenizer, prompt, args.max_new_tokens)
    except (KeyError, OSError, ValueError) as exc:
        parser.exit(1, f"Cannot load or run the bundle: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
