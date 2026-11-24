# Local services finder grounding evaluation

This evaluation checks whether the recommendation response faithfully represents the business data returned by the tools. It does not measure whether those tools retrieved the best providers. See [rubric.md](rubric.md) for the exact issue types, pass definition, and metric denominators.

## Run order

Run commands from the repository root in the project environment.

1. Run the existing queries through the agent and capture complete tool outputs and responses:

   ```powershell
   python eval/scripts/run_system.py eval/data/queries_draft.jsonl --out eval/data/runs/trace_dataset.jsonl --events eval/data/runs/tool_events.jsonl --cache eval/data/runs/tool_response_cache.json --confirm-live
   ```

   This makes live LLM and business API calls unless an exact matching tool response is already in the configured cache. It reuses matching detail/review responses from `eval/data/enrichment_cache.json`. Saved search snapshots are not currently loaded. Run metadata includes the configured intent/cleanup and synthesis models, run commit SHA, dirty-tree state, and per-query elapsed time. To resume an interrupted run, repeat with `--resume` and the same output/cache paths.

2. Prepare a compact evidence view. This leaves `trace_dataset.jsonl` unchanged:

   ```powershell
   python eval/scripts/clean_tool_errors.py eval/data/runs/trace_dataset.jsonl --out eval/data/runs/trace_dataset_cleaned.jsonl
   ```

   The preparation script normalizes tool errors and applies field allowlists. It keeps the request criteria, provider identity and attributes relevant to response claims, up to 10 search results per tool call, three short review snippets per review call, and the final answer/candidate evidence. It drops unused API fields, review authors, old SQL labels, cache metadata, and timings from the judge payload. It prints the size reduction. The judge refuses an unprepared full trace.

3. Judge cases in synchronous groups of five:

   ```powershell
   python eval/scripts/judge_traces.py eval/data/runs/trace_dataset_cleaned.jsonl --batch-size 5 --out eval/data/runs/judged_dataset_grouped.jsonl
   ```

   For 50 evaluated responses, this makes 10 LLM requests. Use `--batch-size 10` for 5 requests. The judge returns provider faithfulness, checked/supported attribute counts, constraint adherence, and evidence-backed issue records. The script computes each case's strict grounding pass. Completed groups are checkpointed; repeat the same command with `--resume` after an interruption.

   This is synchronous grouping of several cases into one prompt. It is not OpenAI's asynchronous Batch API. It reduces the number of requests but does not provide the asynchronous API's token discount. The amount of evidence sent is reduced by step 2.

4. Generate the machine-readable portfolio summary:

   ```powershell
   python eval/scripts/summarize_traces.py eval/data/runs/judged_dataset_grouped.jsonl --out eval/data/runs/eval_summary.json
   ```

   The summary includes the grounding pass rate, supported-provider/attribute/constraint metrics, issue counts and examples, measured latency/tool counts, and judge token usage. It omits dollar cost because agent token use and pricing are not currently captured. GitHub permalinks are emitted only for files that exist in the recorded commit; commit or publish the query dataset, rubric, and results if those links are needed.

## Previously submitted asynchronous batch

The grouped judge script does not change or cancel an OpenAI Batch API job submitted earlier. If that job is still running and no longer wanted, cancel it separately in the OpenAI Platform or with its batch ID. It is independent of this workflow.
