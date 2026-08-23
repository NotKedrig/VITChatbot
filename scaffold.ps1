$initFiles = @(
    'app/__init__.py',
    'app/llm/__init__.py',
    'app/agents/__init__.py',
    'app/rag/__init__.py',
    'app/db/__init__.py',
    'app/db/state/__init__.py',
    'app/scheduler/__init__.py',
    'tests/__init__.py'
)

foreach ($f in $initFiles) {
    $dir = Split-Path $f -Parent
    if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    if (-not (Test-Path $f)) {
        Set-Content -Path $f -Value '# Phase 0 scaffold'
        Write-Host "Created $f"
    } else {
        Write-Host "Already exists: $f"
    }
}

$gitkeepDirs = @(
    'prompts',
    'evaluation/datasets',
    'evaluation/rubrics',
    'evaluation/metrics',
    'experiments',
    'results',
    'analysis/charts',
    'docs',
    'logs',
    'chroma_data',
    'data/raw_docs'
)

foreach ($d in $gitkeepDirs) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    $gk = "$d/.gitkeep"
    if (-not (Test-Path $gk)) {
        New-Item -ItemType File -Path $gk | Out-Null
        Write-Host "Created $gk"
    } else {
        Write-Host "Already exists: $gk"
    }
}

Write-Host "Scaffold complete."
