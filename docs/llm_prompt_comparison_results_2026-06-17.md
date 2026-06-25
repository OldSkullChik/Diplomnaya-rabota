# LLM prompt-only comparison results - 2026-06-17

## Scope

Task: compare the accepted custom ЖКХ/ОМСУ solution with ready free Hugging Face LLMs.

Evaluation mode: prompt-only classification, no fine-tuning. Models receive a fixed test-split record and must return strict JSON with allowed labels.

Local environment: `.venv-ml`, `torch 2.11.0+cu128`, `transformers 5.9.0`, NVIDIA RTX 3050 Ti Laptop GPU, 4 GB VRAM.

Important caveat: this is a screening benchmark on small samples, because several 3B+ prompt runs are too slow on the local 4 GB GPU setup. The result is still enough to decide whether a ready LLM can replace the custom pipeline.

## Custom Baselines

Accepted custom taxonomy cascade:

- Mean macro-F1: about `0.3003-0.3032` on the 8-axis taxonomy test setup.
- Main advantage: deterministic labels, domain rules, integration with the existing ЖКХ taxonomy.

Accepted custom OMSU selective layer:

- Coverage: `0.7496`.
- Accuracy: `0.9939`.
- Macro-F1: `0.9102`.
- Weighted-F1: `0.9937`.
- Negative-class F1: `0.8235`.

## OMSU Negative Signal

| Model | Rows | Parse | Invalid | Accuracy | Macro-F1 | Weighted-F1 | sec/row | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Qwen/Qwen2.5-3B-Instruct | 10 | 1.00 | 0.00 | 0.7000 | 0.6703 | 0.7297 | 18.36 | Best LLM score, but only 10 rows and very slow |
| HuggingFaceTB/SmolLM2-1.7B-Instruct | 20 | 0.85 | 0.15 | 0.7647 | 0.5952 | 0.7647 | 3.71 | Strong among compact models, but JSON is unstable |
| Qwen/Qwen3-1.7B | 20 | 1.00 | 0.00 | 0.6000 | 0.5238 | 0.6571 | 1.55 | Stable after disabling thinking mode |
| HuggingFaceTB/SmolLM3-3B | 10 | 1.00 | 0.00 | 0.5000 | 0.4949 | 0.5253 | 23.84 | Too slow for this hardware |
| Qwen/Qwen2.5-0.5B-Instruct | 20 | 1.00 | 0.00 | 0.8500 | 0.4595 | 0.7811 | 1.00 | High accuracy from class skew, weak macro-F1 |
| Qwen/Qwen3-0.6B | 20 | 0.95 | 0.05 | 0.4737 | 0.4345 | 0.5363 | 2.50 | Needed no-thinking mode |
| Qwen/Qwen2.5-1.5B-Instruct | 20 | 1.00 | 0.00 | 0.4000 | 0.3939 | 0.4364 | 1.79 | Worse than smaller Qwen2.5 on this sample |
| ai-forever/rugpt3small_based_on_gpt2 | 20 | 0.00 | 1.00 | 0.0000 | 0.0000 | 0.0000 | 1.68 | Base GPT, not instruction-following enough |
| TinyLlama/TinyLlama-1.1B-Chat-v1.0 | 20 | 0.00 | 1.00 | 0.0000 | 0.0000 | 0.0000 | 6.04 | Did not produce valid task JSON |

`microsoft/Phi-3.5-mini-instruct` was also attempted. It first failed with a `DynamicCache` compatibility error, then with `attn_implementation=eager` and `use_cache=False` did not finish a 10-row run within about 7 minutes and was killed. On this hardware it is not practical for this prompt-only setup.

## 8-Axis Taxonomy

| Model | Rows | Parse | Invalid | Mean macro-F1 | sec/row | Notes |
|---|---:|---:|---:|---:|---:|---|
| Qwen/Qwen3-1.7B | 20 | 1.00 | 0.00 | 0.2121 | 6.86 | Best screened ready LLM for taxonomy |
| Qwen/Qwen2.5-0.5B-Instruct | 20 | 1.00 | 0.40 | 0.1797 | 4.31 | Many invalid labels |
| HuggingFaceTB/SmolLM2-1.7B-Instruct | 5 | 0.40 | 0.80 | 0.1285 | 8.57 | Full 20-row run timed out; short run also unstable |
| Qwen/Qwen2.5-1.5B-Instruct | 20 | 1.00 | 0.10 | 0.1105 | 5.32 | Stable JSON, poor label quality |

`Qwen/Qwen2.5-3B-Instruct` was attempted on taxonomy with 10 rows, but did not finish within about 10 minutes and was killed.

## Conclusion

Ready free LLMs from Hugging Face do not replace the custom solution for this project.

For OMSU, the best screened LLM reached `0.6703` macro-F1 on only 10 rows at `18.36` seconds per row, while the accepted custom OMSU layer has `0.9102` macro-F1 on its selective test setup and is operationally much more suitable.

For the 8-axis taxonomy, the best screened LLM reached only `0.2121` mean macro-F1, below the accepted custom cascade range of about `0.3003-0.3032`, and with much worse inference cost.

Practical decision: keep the custom cascade and OMSU selective layer as the production/research solution. Ready LLMs can still be useful as auxiliary tools for weak labeling, annotation suggestions, prompt experiments, or qualitative explanation drafts, but not as a direct replacement for the trained ЖКХ/ОМСУ pipeline.
