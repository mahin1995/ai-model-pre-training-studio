"""Assemble an evaluated checkpoint, report and model card for local release."""

import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from ..training.core import config_hash
from ..training.data import digest
from .local import verify_file


def package_release(bundle, evaluation, card, output, step=None):
    manifest_path = bundle / "manifest.json"
    training = json.loads(manifest_path.read_text())
    settings = training["configuration"]
    step = step if step is not None else training["report"]["completedSteps"]
    checkpoint = bundle / "checkpoints" / f"step-{step:06d}"
    descriptor_path = checkpoint / "checkpoint.json"
    descriptor = json.loads(descriptor_path.read_text())
    if (descriptor["step"] != step or descriptor["configHash"] != config_hash(settings)
            or descriptor["sourceIdentity"] != training["source"]["sourceIdentity"]):
        raise ValueError("The checkpoint does not match the training bundle.")
    tokenizer = bundle / "tokenizer.json"
    verify_file(tokenizer, training["artifacts"]["tokenizer"])
    model_hash = descriptor["files"]["model.safetensors"]["sha256"]
    report = json.loads(evaluation.read_text())
    if report["settings"]["metricScope"] != "final-test" or report["tokenizerSha256"] != digest(tokenizer):
        raise ValueError("Supply a final-test comparison using the same tokenizer.")
    candidates = {result["modelSha256"] for result in report["results"]
                  if result["metrics"] and result["metrics"]["heldOutAvailable"] and result["weightsUnchanged"]}
    if len(candidates) < 2 or model_hash not in candidates:
        raise ValueError("The selected model must appear in a completed comparison with another model.")
    if not card.read_text().strip():
        raise ValueError("Supply a model card with evaluation decisions, usage scope and limitations.")

    files = {"manifest.json": manifest_path, "tokenizer.json": tokenizer, "model-card.md": card,
             "evaluation.json": evaluation, "report.json": bundle / "report.json",
             f"checkpoints/{checkpoint.name}/checkpoint.json": descriptor_path}
    for filename in ("model.safetensors", "config.json", "generation_config.json"):
        if filename in descriptor["files"] or filename != "generation_config.json":
            path = checkpoint / filename
            verify_file(path, descriptor["files"][filename])
            files[f"checkpoints/{checkpoint.name}/{filename}"] = path
    verify_file(files["report.json"], training["artifacts"]["report"])
    release = {"schemaVersion": 1, "step": step, "modelSha256": model_hash,
               "templateVersion": settings.get("templateVersion"), "runtime": descriptor["versions"],
               "sha256": {name: digest(path) for name, path in files.items()}}
    with NamedTemporaryFile(dir=output.parent, prefix=".studio-release-", suffix=".zip", delete=False) as staged:
        temporary = Path(staged.name)
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            for name, path in files.items():
                archive.write(path, name)
            archive.writestr("release.json", json.dumps(release, sort_keys=True, indent=2) + "\n")
        output.hardlink_to(temporary)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Extracted training bundle")
    parser.add_argument("evaluation", type=Path, help="Downloaded final-test evaluation report JSON")
    parser.add_argument("card", type=Path, help="Reviewed model card Markdown")
    parser.add_argument("output", type=Path, help="New release ZIP")
    parser.add_argument("--step", type=int)
    args = parser.parse_args()
    try:
        package_release(args.bundle, args.evaluation, args.card, args.output, args.step)
    except (KeyError, OSError, ValueError) as exc:
        parser.exit(1, f"Cannot package the release: {exc}\n")


if __name__ == "__main__":
    main()
