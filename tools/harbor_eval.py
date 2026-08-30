#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.harbor.framework.generate import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    EvalBuildError,
    materialize_eval,
    tree_digest,
)
from evals.harbor.framework.validate import validate_task  # noqa: E402


def _generate(args: argparse.Namespace) -> int:
    task_dir = materialize_eval(
        args.slug,
        output_root=args.output_root,
        image_ref=args.image_ref,
    )
    validate_task(task_dir)
    print(task_dir)
    return 0


def _validate(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="typewriter-harbor-validate-") as temp_dir:
        output_root = Path(temp_dir)
        first_task = materialize_eval(args.slug, output_root=output_root / "first", image_ref=args.image_ref)
        second_task = materialize_eval(args.slug, output_root=output_root / "second", image_ref=args.image_ref)
        validate_task(first_task)
        validate_task(second_task)
        first_digest = tree_digest(first_task)
        second_digest = tree_digest(second_task)
        if first_digest != second_digest:
            raise EvalBuildError("repeated materialization produced different task trees")

        if args.harbor_import_check:
            subprocess.run(
                [
                    args.harbor_python,
                    "-c",
                    ("from pathlib import Path; " "from harbor.models.task.task import Task; " "Task(Path(__import__('sys').argv[1]))"),
                    str(first_task),
                ],
                check=True,
            )

    print(f"{args.slug}: deterministic task digest {first_digest}")
    return 0


def _assert_reward(args: argparse.Namespace) -> int:
    result_paths = sorted(args.job_dir.glob("*/result.json"))
    if len(result_paths) != 1:
        raise EvalBuildError("control job must contain exactly one trial result file")

    trial_result = json.loads(result_paths[0].read_text())
    if trial_result.get("exception_info") is not None:
        raise EvalBuildError(f"control trial raised an exception: {trial_result['exception_info']}")
    verifier_result = trial_result.get("verifier_result")
    rewards = verifier_result.get("rewards") if isinstance(verifier_result, dict) else None
    actual_reward = rewards.get("reward") if isinstance(rewards, dict) else None
    if actual_reward != args.expected:
        raise EvalBuildError(f"expected reward {args.expected:g}, received {actual_reward!r}")

    print(f"{args.job_dir}: reward {actual_reward:g}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and validate Typewriter Harbor maintenance evals.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Materialize one eval as a Harbor task.")
    generate_parser.add_argument("slug")
    generate_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    generate_parser.add_argument("--image-ref")
    generate_parser.set_defaults(handler=_generate)

    validate_parser = subparsers.add_parser("validate", help="Check deterministic generation and task structure.")
    validate_parser.add_argument("slug")
    validate_parser.add_argument("--image-ref")
    validate_parser.add_argument("--harbor-import-check", action="store_true")
    validate_parser.add_argument(
        "--harbor-python",
        default=sys.executable,
        help="Python interpreter with Harbor installed, used with --harbor-import-check.",
    )
    validate_parser.set_defaults(handler=_validate)

    reward_parser = subparsers.add_parser("assert-reward", help="Assert one Harbor control job's reward.")
    reward_parser.add_argument("job_dir", type=Path)
    reward_parser.add_argument("expected", type=float, choices=(0.0, 1.0))
    reward_parser.set_defaults(handler=_assert_reward)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        return int(args.handler(args))
    except (EvalBuildError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
