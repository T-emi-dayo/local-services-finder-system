# Tool-output grounding rubric

## Scope

Judge each agent response only against its query and the business tool outputs captured for that run. This evaluates response grounding and constraint handling. It does not evaluate whether the search API found all or the best available providers.

## Issue types

- `fabricated_provider`: a business named in the response is absent from all captured business search/detail/review outputs.
- `wrong_attribute`: a factual provider attribute in the response conflicts with the captured outputs, such as address, phone, service category, rating, hours, price signal, website, email, or review information.
- `unsupported_claim`: a factual claim is not supported by the captured outputs, even when the outputs do not directly contradict it.
- `ignored_constraint`: the response silently changes or ignores the requested service, location, or stated constraints, instead of qualifying the result or explaining the mismatch.

Use short excerpts from the exact compact tool evidence and final response for every issue. Do not invent missing evidence. A response can have multiple issue records.

## Case-level measures

- `provider_faithfulness`: true only when every named business occurs in captured tool output.
- `attributes_checked`: count of factual provider attributes stated in the final response; do not count conversational wording.
- `attributes_supported`: count of those attributes that are directly supported by the tool output.
- `attribute_accuracy`: total supported attributes divided by total checked attributes. It is unavailable when no provider attributes were stated.
- `has_unsupported_claim`: true if the case has one or more `unsupported_claim` issues.
- `constraint_adherence`: true when the response respects the request or transparently explains that captured results do not satisfy it.
- `grounding_pass`: computed by the evaluation script. A case passes only when there are no issues, all providers are faithful, all checked attributes are supported, and constraints are respected.

## Aggregate metrics

- `grounding_pass_rate`: passed judged cases divided by all judged cases.
- `provider_faithfulness`: share of judged cases with `provider_faithfulness=true`.
- `attribute_accuracy`: total supported attributes divided by total checked attributes across cases.
- `unsupported_claim_rate`: share of judged responses containing at least one unsupported claim.
- `constraint_adherence`: share of judged cases with `constraint_adherence=true`.

Issue counts are occurrences, so one response can count more than once or under more than one issue type. Failed agent runs without a final response are excluded from grounding metrics and reported separately.
