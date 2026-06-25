# LLM comparison plan - 2026-06-17

## Goal

Compare the accepted custom ЖКХ/ОМСУ solution with free Hugging Face LLMs.

Scope is intentionally narrow: only causal/chat/instruction `text-generation` models. No BERT, RoBERTa, NLI encoders, or embedding models.

The LLMs are evaluated as ready prompt-based classifiers: no fine-tuning, no extra training.

## Project baseline

Accepted custom taxonomy checkpoint:

`data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/`

Accepted custom OMSU checkpoint:

`data/ml_experiments/omsu_score_2026-06-06/threshold/negative_signal_capped_20k/`

Important baseline numbers from the current project reports:

- 8-axis taxonomy/cascade remains around `0.3003-0.3032` mean test macro-F1.
- OMSU selective layer: coverage `0.7496`, accuracy `0.9939`, macro-F1 `0.9102`, weighted-F1 `0.9937`, negative F1 `0.8235`.

The LLM question is: can a ready LLM produce reliable structured labels for this domain without the custom trained pipeline?

## LLM models selected

| # | Model | Why it was selected | Link |
|---:|---|---|---|
| 1 | `Qwen/Qwen2.5-0.5B-Instruct` | Smallest practical Qwen instruct baseline; should run fastest and shows the low-end LLM floor. | https://hf.co/Qwen/Qwen2.5-0.5B-Instruct |
| 2 | `Qwen/Qwen2.5-1.5B-Instruct` | Middle Qwen size; useful tradeoff between speed and instruction following. | https://hf.co/Qwen/Qwen2.5-1.5B-Instruct |
| 3 | `Qwen/Qwen2.5-3B-Instruct` | Stronger Qwen2.5 local candidate; good test of whether a compact LLM can replace the custom classifier. | https://hf.co/Qwen/Qwen2.5-3B-Instruct |
| 4 | `Qwen/Qwen3-0.6B` | Newer Qwen3 small model; checks whether newer generation beats older Qwen2.5 at similar size. | https://hf.co/Qwen/Qwen3-0.6B |
| 5 | `Qwen/Qwen3-1.7B` | Newer Qwen3 mid-size model; likely one of the most realistic local prompt-only candidates. | https://hf.co/Qwen/Qwen3-1.7B |
| 6 | `TinyLlama/TinyLlama-1.1B-Chat-v1.0` | Classic tiny chat LLM; useful as a weak but lightweight open baseline. | https://hf.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0 |
| 7 | `HuggingFaceTB/SmolLM2-1.7B-Instruct` | Modern small instruction LLM from HF; tests a non-Qwen small model. | https://hf.co/HuggingFaceTB/SmolLM2-1.7B-Instruct |
| 8 | `HuggingFaceTB/SmolLM3-3B` | Multilingual SmolLM generation with Russian listed in metadata; relevant for Russian ЖКХ comments. | https://hf.co/HuggingFaceTB/SmolLM3-3B |
| 9 | `microsoft/Phi-3.5-mini-instruct` | Strong small multilingual instruction model with MIT license; important non-Qwen baseline. | https://hf.co/microsoft/Phi-3.5-mini-instruct |
| 10 | `ai-forever/rugpt3small_based_on_gpt2` | Russian generative baseline; not instruction-tuned, so it tests whether Russian pretraining alone is enough. | https://hf.co/ai-forever/rugpt3small_based_on_gpt2 |
| 11 | `Qwen/Qwen3-4B-Instruct-2507` | Heavier newer Qwen3 instruct model; likely stronger, but difficult on 4 GB VRAM. | https://hf.co/Qwen/Qwen3-4B-Instruct-2507 |
| 12 | `ai-forever/Pollux-4B-Judge` | Russian 4B judge-style model; interesting because the task is close to judgment/scoring. | https://hf.co/ai-forever/Pollux-4B-Judge |
| 13 | `IlyaGusev/saiga_llama3_8b` | Russian instruction LLM; important domain-language candidate, but heavy for the laptop. | https://hf.co/IlyaGusev/saiga_llama3_8b |
| 14 | `google/gemma-3-1b-it` | Gated Gemma 1B instruction model; useful only after accepting the HF license. | https://hf.co/google/gemma-3-1b-it |
| 15 | `google/gemma-2-2b-it` | Gated Gemma 2B instruction model; strong compact baseline, but requires license acceptance. | https://hf.co/google/gemma-2-2b-it |

## Download commands

Dry-run, no files downloaded:

```powershell
.\experiments\download_hf_comparison_models_2026_06_17.ps1 -DryRun
```

Download the 10 core non-gated LLMs:

```powershell
.\experiments\download_hf_comparison_models_2026_06_17.ps1
```

Also include heavier non-gated LLMs:

```powershell
.\experiments\download_hf_comparison_models_2026_06_17.ps1 -IncludeHeavy
```

Also include gated Gemma models after accepting their HF license:

```powershell
.\experiments\download_hf_comparison_models_2026_06_17.ps1 -IncludeGated
```

One-model pattern:

```powershell
$HF = ".\.venv-ml\Scripts\hf.exe"
& $HF download Qwen/Qwen2.5-0.5B-Instruct `
  --local-dir data\hf_models\Qwen__Qwen2.5-0.5B-Instruct `
  --exclude "tf_model.*" `
  --exclude "flax_model.*" `
  --exclude "*.onnx" `
  --exclude "onnx/*" `
  --exclude "openvino/*" `
  --exclude "pytorch_model.bin"
```

## Prompt-only evaluation commands

Start with OMSU because it is binary and directly comparable to the strongest custom layer:

```powershell
.\.venv-ml\Scripts\python.exe experiments\run_llm_prompt_comparison_2026_06_17.py `
  --model Qwen/Qwen2.5-0.5B-Instruct `
  --task omsu `
  --max-samples 50 `
  --prefer-local
```

Then test the full 8-axis taxonomy on a smaller slice:

```powershell
.\.venv-ml\Scripts\python.exe experiments\run_llm_prompt_comparison_2026_06_17.py `
  --model Qwen/Qwen2.5-0.5B-Instruct `
  --task taxonomy `
  --max-samples 25 `
  --prefer-local
```

Use CPU fallback for models that do not fit in 4 GB VRAM:

```powershell
.\.venv-ml\Scripts\python.exe experiments\run_llm_prompt_comparison_2026_06_17.py `
  --model microsoft/Phi-3.5-mini-instruct `
  --task omsu `
  --max-samples 30 `
  --prefer-local `
  --device cpu `
  --trust-remote-code
```

Outputs:

`data/ml_experiments/llm_prompt_comparison_2026-06-17/<task>/<model_slug>/metrics.json`

## Metrics

For each LLM:

- parse rate: how often the model returned valid JSON,
- invalid-label rate: how often it invented labels outside the allowed set,
- accuracy,
- macro-F1,
- weighted-F1,
- seconds per row.

The key comparison is not only F1. If an LLM has okay F1 but poor JSON/label stability, it is not a safe replacement for the production classifier.
