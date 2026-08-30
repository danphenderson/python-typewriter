# Typewriter Harbor maintenance evals

This directory turns ordinary Typewriter development work into reproducible
[Harbor](https://www.harborframework.com/) repository-maintenance evaluations.
Harbor remains the external orchestrator. The reusable image contains only the
pinned maintenance toolchain; every task supplies its own baseline snapshot,
instruction, hidden verifier, and Oracle patch.

Generated Docker tasks are offline at execution time. Harbor 0.21 labels the
task policy `public` because its sidecar-backed `no-network` mode is unavailable
on Docker hosts without the required nftables kernel support; the generated
Compose overlay independently applies Docker's native `network_mode: none` to
the main container. `UV_OFFLINE=1` and `PIP_NO_INDEX=1` add a second fail-closed
dependency-installation boundary inside the image.

## Layout

- `image/`: the reusable, multi-Python maintenance image and dependency lock.
- `framework/`: deterministic task generation, repository bootstrap, and grading.
- `specs/`: human-reviewed eval definitions derived from normal development work.
- `build/harbor/tasks/`: generated Harbor tasks; ignored through the repository's
  existing `build/` rule.

## Local workflow

Build the image from the repository root:

```bash
docker build \
  --file evals/harbor/image/Dockerfile \
  --tag python-typewriter-harbor:maintenance-v2 \
  .
```

Generate and statically validate every committed task in sorted order:

```bash
python tools/harbor_eval.py list
python tools/harbor_eval.py generate-all
python tools/harbor_eval.py validate-all
```

If Harbor is installed, include Harbor's native task-loading checks without
invoking an agent or model:

```bash
python tools/harbor_eval.py validate-all \
  --harbor-import-check \
  --harbor-python /path/to/harbor/python
```

Run the negative control and Oracle:

```bash
harbor run -p build/harbor/tasks/python310-toml-fallback -a nop \
  -o build/harbor/jobs --job-name nop-control --yes
python tools/harbor_eval.py assert-reward build/harbor/jobs/nop-control 0

harbor run -p build/harbor/tasks/python310-toml-fallback -a oracle \
  -o build/harbor/jobs --job-name oracle-control --yes
python tools/harbor_eval.py assert-reward build/harbor/jobs/oracle-control 1
```

The no-op trial must receive reward `0`; the Oracle trial must receive reward
`1`. Verifier logs include targeted and regression JUnit reports. Downloaded
artifacts include individual gate logs, package output, repository status, and
the agent's final patch.

## Adding an eval during development

1. Write the maintenance request as `specs/<slug>/instruction.md`.
2. Add the normal regression test while implementing the fix, then copy or adapt
   the black-box portion under `specs/<slug>/hidden_tests/`.
3. Pin the healthy pre-change commit as `base_ref` and the reviewed fix as
   `solution_ref` in `spec.toml`.
4. Limit `solution_paths` to product files. Tests, eval machinery, and solution
   assets are rejected as Oracle patch inputs.
5. Run deterministic generation, Harbor checks, the no-op control, and Oracle.

Commits are provenance boundaries, not automatic task boundaries. Prefer one
coherent maintenance intent per eval even when a development commit addressed
several concerns.

## Image lifecycle

Normal Typewriter source changes do not rebuild the image. Rebuild it when the
image contract, dependency lock, Python support matrix, pre-commit environment,
or system tooling changes. Local tasks use `python-typewriter-harbor:maintenance-v2`.
Published tasks must override that reference with an immutable registry digest:

```bash
python tools/harbor_eval.py generate <slug> \
  --image-ref ghcr.io/danphenderson/python-typewriter-harbor@sha256:<digest>
```

The Linux image complements the native Linux/macOS project CI matrix; it does
not replace cross-platform release qualification. The dedicated
`harbor-maintenance.yml` workflow rebuilds the image and enforces deterministic
generation plus the no-op and Oracle controls when framework inputs change.
