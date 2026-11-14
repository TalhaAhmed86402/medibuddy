# Support and operations (maintainers)

How student questions, bug reports and scoring disputes are handled once the benchmark is in use.

## Channels
- **GitHub issues** with the templates in `.github/ISSUE_TEMPLATE/`: *bug report*, *scoring dispute*, *integration question*.
  Every template asks for the data version, the command, and the episode id, so most issues can be reproduced with one command.
- Answers that more than one team needs go into `docs/FAQ.md`.

## Triage of an issue
1. Reproduce: `python -m medibuddy_bench verify --data data/dev` (is their checkout intact?), then the reported command on the
   reported episode (`run --agent ... --tasks T5 --ids <id>` style runs are possible through `Runner.run(ids=...)`).
2. Classify:
   - *integration problem* (agent never calls tools, wrong format, A2A version): answer, add to the FAQ if new;
   - *scorer bug* (a correct reply marked wrong, or a wrong reply accepted): fix with a regression test, release a new data
     version (scores change), note it in `CHANGELOG.md`;
   - *data bug* (an impossible or contradictory scenario): fix the generator, regenerate, new data version;
   - *not a bug* (the reply really was wrong): explain with the scorer's `checks` for that episode.
3. Close the issue with the version that contains the fix.

## Releasing a fix
Follow the versioning policy in `CHANGELOG.md`: bump `VERSION`, regenerate (`make data SPLIT=dev`, `make data SPLIT=lite`), re-run
baselines (`make baselines SPLIT=dev`), `python scripts/dataset_stats.py --write`, run the tests, add the changelog entry, tag
`v<version>` (the publish workflow pushes the Docker image). Announce that older runs are now stale and re-run ranked agents on the
hidden split.

## The hidden split
Build it once per data version with the private seed (and optionally the private phrase file, `docs/HELDOUT_PHRASES.md`), keep it
outside the repository, serve it with `serve --data /private/test --runs-dir /private/runs`, and publish only the leaderboard
built from those runs (`docs/LEADERBOARD.md`). Never send it to a model provider that may train on prompts.
