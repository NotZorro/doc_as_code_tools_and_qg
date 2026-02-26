# Запуск (RUN)

Здесь: локальный запуск, Docker‑запуск, примеры команд и типовой workflow.

## 1) Локально (Python venv)

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .

doc-quality --help
```

## 2) Docker: сборка локального образа

```bash
docker build -t docq:local .
```

> Если сборка ломается на `python:3.11-slim` из DockerHub (корп‑сеть), используйте:
> - proxy cache в вашем Harbor
> - либо заранее `docker load` базового образа (offline).
> Подробнее: docs/TROUBLESHOOTING.md.

## 3) Docker: запуск (PowerShell)

**Важно:** маппинг путей под Windows PowerShell делайте так:
- `-v "$($PWD.Path):/work"` (а не `${PWD}`)

### 3.1 Quality Gate: по директории

```powershell
$IMAGE="docq:local"

docker run --rm `
  -v "$($PWD.Path):/work" `
  -w /work `
  $IMAGE `
  run `
    --paths ./docs `
    --policy-root ./.docq `
    --pbc quality_gate `
    --out-dir ./reports
```

### 3.2 Quality Gate: по paths-file (самый надёжный способ, включая пробелы)

```powershell
@(
  "docs/product offering/features/Feature-0001.md"
  "docs/product offering/api/API-0001.md"
) | Set-Content -Encoding utf8 .\changed_paths.txt

docker run --rm `
  -v "$($PWD.Path):/work" `
  -w /work `
  $IMAGE `
  run `
    --paths-file ./changed_paths.txt `
    --policy-root ./.docq `
    --pbc quality_gate `
    --out-dir ./reports
```

### 3.3 Test Design (single)

```powershell
$env:LLMOPS_API_KEY="***"
$IMAGE="docq:local"

docker run --rm `
  -e LLMOPS_API_KEY="$env:LLMOPS_API_KEY" `
  -v "$($PWD.Path):/work" `
  -w /work `
  $IMAGE `
  test-design `
    --feature "./docs/features/Feature-0001.md" `
    --bundle auto `
    --paths ./docs `
    --policy-root ./.docq `
    --pbc test_design `
    --out-dir ./reports `
    --include-negative `
    --include-edge
```

### 3.4 Test Design (split B1)

```powershell
$env:LLMOPS_API_KEY="***"
$IMAGE="docq:local"

docker run --rm `
  -e LLMOPS_API_KEY="$env:LLMOPS_API_KEY" `
  -v "$($PWD.Path):/work" `
  -w /work `
  $IMAGE `
  test-design `
    --mode split `
    --split-by doc_type `
    --feature "./docs/features/Feature-0001.md" `
    --bundle auto `
    --paths ./docs `
    --policy-root ./.docq `
    --pbc test_design `
    --out-dir ./reports `
    --doc-types feature,api,algorithm,service `
    --generators-map "feature=test_design_e2e_v1,api=test_design_api_v1,algorithm=test_design_algorithm_v1,service=test_design_service_v1" `
    --max-input-chars 12000 `
    --max-scenarios 12 `
    --include-negative `
    --include-edge `
    --emit-plan `
    --keep-fragments
```

## 4) Где смотреть результаты

По умолчанию всё в одной папке `--out-dir` (layout=flat).

```powershell
Get-ChildItem .\reports -File | Select-Object Name
code .\reports\td.*.coverage.md
code .\reports\qg.summary.json
```

## 5) Переменные окружения

Engine читает:
- `LLMOPS_API_KEY` — ключ (обязателен для LLM).
- `LLMOPS_BASE_URL` — base_url (по умолчанию `https://api.openai.com/v1`).
- `LLM_MODEL` — форсит модель поверх policy.
- `LLM_CA_PEM` — путь к CA сертификату (если ваш gateway требует).
- `HTTP_PROXY/HTTPS_PROXY/NO_PROXY` — если сеть требует прокси.

