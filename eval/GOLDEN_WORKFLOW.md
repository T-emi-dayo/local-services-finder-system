# Golden and synthetic dataset workflow

The complete ordered commands are in [README.md](README.md). The workflow is:

1. Generate seed goldens from the existing real provider records.
2. Use DeepEval to synthesize 50 test goldens from those seed goldens.
3. Run each synthetic query through the actual graph, reusing saved search data and invoking cached detail/review enrichment tools.
4. Compare actual responses with expected outputs using DeepEval G-Eval.

The generator scripts make LLM calls only when you run them. The system replay never repeats business searches; it requires explicit confirmation because detail and review tools can consume business API quota. No generation, replay, or scoring call was run while preparing these scripts.
