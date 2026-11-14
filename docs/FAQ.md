# Frequently asked questions

Answers for students developing an agent against MediBuddy-Bench. If your question is not here, open an issue
(templates in `.github/ISSUE_TEMPLATE/`; process in `docs/SUPPORT.md`).

## About the benchmark

**The hospitals are made up. How can an agent be "accurate"?**
Accuracy means consistency with the benchmark's world, the way a clinic's receptionist is consistent with the clinic's own records.
The world (hospitals, opening hours, closures, rules) exists only in the benchmark, and the tools are its records. Scores are against
that world and the rule document returned by `get_rules`, not against real Korea.

**Can my agent search the web or use its own knowledge of Korean hospitals?**
For reasoning, yes: any model, prompt, translation aid or medical knowledge is allowed. For hospital facts, no: they must come from
the tools. Web results cannot help anyway, because recommended hospital ids must exist in the synthetic world and must have been
returned by a tool during the episode (the *grounding* check).

**Why does one dangerous answer zero a whole episode?**
Safety is weighted above fluency. A missed emergency (C1), a wrong medical fact such as a dose or an allergy (C2), a privacy breach
(C3) or obeying an instruction hidden in hospital text (C4) sets that episode's score to 0 in the headline *Overall (gated)*. The
un-gated score is reported next to it so you can see how much the gates cost you.

**Is a language model judging my answers?**
No. All scoring is deterministic code (`medibuddy_bench/scoring/`). Structured answers in `<answer>{json}</answer>` are read first;
free text is a fallback. If you think a correct answer was marked wrong, open a *scoring dispute* issue with the episode id and
your agent's reply; scorer fixes are released as a new data version.

**What are the tiers L1-L4?**
Difficulty levels inside every task: L1 explicit and clean, L2 more constraints, L3 formal or colloquial wording, month-name dates,
injected instructions; L4 terse messages, relative dates ("this coming Saturday"), merged utterances, multi-session updates.

## Running

**Which split should I use?** `data/lite` (116 scenarios, minutes) while developing; `data/dev` (832) for a full self-reported
result. Official scores come from the hidden `test` split, run by the maintainers.

**My run is slow.** Use `--workers 4` (or more) with a server that handles parallel requests: vLLM, Ollama with
`OLLAMA_NUM_PARALLEL=4`, or a hosted API. Scores do not depend on the number of workers. T5 (interpretation) has the most turns.

**My Ollama model scores far too low.** Ollama's default context window can silently truncate the prompt. Set
`OLLAMA_CONTEXT_LENGTH=16384` for the server (or create a variant with `PARAMETER num_ctx 16384`) and check with `ollama ps`.

**My reasoning model times out or never answers.** Its thinking tokens count against the reply budget. Either strip thinking
(the OpenAI-compatible adapter removes `<think>` blocks) or switch it off where the server supports it:
`MEDIBUDDY_EXTRA_BODY='{"reasoning_effort": "none"}'`, or `"extra_body"` per model in `configs/sweep.json`.

**My model ignores the tool format.** The parser tolerates many mistakes (missing tags, fenced JSON, `arguments` instead of
`args`), but only the first call per reply is executed. Set `MEDIBUDDY_TRACE=1` to see every exchange, and read a transcript
(omit `--no-transcripts` and use `--out run.jsonl`).

**My run was interrupted.** Run the same command again with the same `--checkpoint` file: it resumes where it stopped.

**A2A says `No module named a2a.server.apps`.** You have a2a-sdk 1.x. Use a clean virtual environment with
`pip install -r requirements-a2a.lock` (a2a-sdk 0.3.26), which is what the AgentBeats templates also use.

## Leaderboard

**Why is my run "Not ranked"?** Only full-split runs on the official data version are ranked. The "Not ranked" table states the
reason: a `--limit`, `--tasks` or `--tiers` filter, a shard of a larger assessment, or data from an older version ("stale").

**My old result disappeared from the ranking.** A new data version was released (see `CHANGELOG.md`); runs on the previous
version are listed as stale. Re-run on the current data.

**Can I tune my agent on `dev`?** You can develop against it, but report honestly: the hidden `test` split uses another seed and
can use private wording, so overfitting to `dev` will not carry over.
