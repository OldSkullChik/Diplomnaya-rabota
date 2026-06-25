param(
    [switch]$IncludeHeavy,
    [switch]$IncludeGated,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$hf = ".\.venv-ml\Scripts\hf.exe"
if (-not (Test-Path $hf)) {
    throw "HF CLI not found at $hf. Use the project .venv-ml environment."
}

New-Item -ItemType Directory -Force -Path "data\hf_models" | Out-Null
$env:HF_XET_HIGH_PERFORMANCE = "1"

$commonExclude = @(
    "tf_model.*",
    "flax_model.*",
    "*.h5",
    "*.onnx",
    "onnx/*",
    "openvino/*",
    "*.gguf"
)

$models = @(
    @{ Id = "Qwen/Qwen2.5-0.5B-Instruct"; Dir = "Qwen__Qwen2.5-0.5B-Instruct"; Note = "small-qwen"; ExcludeBin = $true },
    @{ Id = "Qwen/Qwen2.5-1.5B-Instruct"; Dir = "Qwen__Qwen2.5-1.5B-Instruct"; Note = "mid-qwen"; ExcludeBin = $true },
    @{ Id = "Qwen/Qwen2.5-3B-Instruct"; Dir = "Qwen__Qwen2.5-3B-Instruct"; Note = "large-local-qwen"; ExcludeBin = $true },
    @{ Id = "Qwen/Qwen3-0.6B"; Dir = "Qwen__Qwen3-0.6B"; Note = "new-small-qwen"; ExcludeBin = $true },
    @{ Id = "Qwen/Qwen3-1.7B"; Dir = "Qwen__Qwen3-1.7B"; Note = "new-mid-qwen"; ExcludeBin = $true },
    @{ Id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"; Dir = "TinyLlama__TinyLlama-1.1B-Chat-v1.0"; Note = "tiny-chat"; ExcludeBin = $true },
    @{ Id = "HuggingFaceTB/SmolLM2-1.7B-Instruct"; Dir = "HuggingFaceTB__SmolLM2-1.7B-Instruct"; Note = "small-instruct"; ExcludeBin = $true },
    @{ Id = "HuggingFaceTB/SmolLM3-3B"; Dir = "HuggingFaceTB__SmolLM3-3B"; Note = "multilingual-ru"; ExcludeBin = $true },
    @{ Id = "microsoft/Phi-3.5-mini-instruct"; Dir = "microsoft__Phi-3.5-mini-instruct"; Note = "multilingual-mini"; ExcludeBin = $true },
    @{ Id = "ai-forever/rugpt3small_based_on_gpt2"; Dir = "ai-forever__rugpt3small_based_on_gpt2"; Note = "russian-base-gpt" }
)

$heavyModels = @(
    @{ Id = "Qwen/Qwen3-4B-Instruct-2507"; Dir = "Qwen__Qwen3-4B-Instruct-2507"; Note = "new-qwen-4b"; ExcludeBin = $true },
    @{ Id = "ai-forever/Pollux-4B-Judge"; Dir = "ai-forever__Pollux-4B-Judge"; Note = "russian-judge-4b"; ExcludeBin = $true },
    @{ Id = "IlyaGusev/saiga_llama3_8b"; Dir = "IlyaGusev__saiga_llama3_8b"; Note = "russian-instruct-8b"; ExcludeBin = $true }
)

$gatedModels = @(
    @{ Id = "google/gemma-3-1b-it"; Dir = "google__gemma-3-1b-it"; Note = "gated-gemma-1b"; ExcludeBin = $true },
    @{ Id = "google/gemma-2-2b-it"; Dir = "google__gemma-2-2b-it"; Note = "gated-gemma-2b"; ExcludeBin = $true }
)

if ($IncludeHeavy) {
    $models += $heavyModels
}
if ($IncludeGated) {
    $models += $gatedModels
}

foreach ($model in $models) {
    $target = Join-Path "data\hf_models" $model.Dir
    $argsList = @("download", $model.Id)
    if (-not $DryRun) {
        $argsList += @("--local-dir", $target)
    }
    foreach ($pattern in $commonExclude) {
        $argsList += @("--exclude", $pattern)
    }
    if ($model.ExcludeBin) {
        $argsList += @("--exclude", "pytorch_model.bin")
    }
    if ($DryRun) {
        $argsList += "--dry-run"
    }

    Write-Host ""
    Write-Host "==> $($model.Id) [$($model.Note)]"
    & $hf @argsList
}
