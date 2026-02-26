# doc-quality / Doc-as-code Quality & Test Design Engine

Этот репозиторий содержит **движок** (engine) для двух больших задач:

1) **Quality Gate** для docs-as-code: правила + (опционально) LLM‑валидаторы секций.
2) **Test Design**: генерация test suite (канонический JSON + Markdown), включая split‑режим (B1 Map→Reduce) по `doc_type`.

Философия простая:
- **Engine** живёт здесь (Python + Docker, CLI).
- **Policy / PBC** живёт в репозитории с документацией (ветка/папка `.docq/`): шаблоны, валидаторы, генераторы, промпты, схемы.

## Быстрые ссылки
- Как запускать: **docs/RUN.md**
- Как настраивать policy (PBC, шаблоны, валидаторы, генераторы, промпты): **docs/POLICY.md**
- CLI справочник (все команды и параметры): **docs/CLI.md**
- Как дорабатывать код (архитектура, где что править, как добавлять capability/renderer): **docs/DEVELOPMENT.md**
- Типовые проблемы (Docker/DNS/timeout/LLM): **docs/TROUBLESHOOTING.md**

---

## TL;DR: что получается на выходе

### Quality Gate (`doc-quality run`)
По умолчанию `--layout flat`:
- `reports/qg.summary.json`
- `reports/qg.<slug>.report.json` (на каждый документ)

### Test Design (`doc-quality test-design`)
По умолчанию `--layout flat`:
- single mode: `reports/td.<generator>.<result_id>.test_suite.(json|md)`
- split mode:  `reports/td.<group>.<result_id>.test_suite.(json|md)`
- coverage (split): `reports/td.<result_id>.coverage.(json|md)`
- plan/debug: `reports/td.<result_id>.plan.json` и `reports/td.<result_id>.*.fragment.json` (если включено)

---

## Минимальный запуск (Docker, PowerShell)

```powershell
$env:LLMOPS_API_KEY="***"
$IMAGE="docq:local"  # или ваш собранный тег

# Quality Gate на примерах
docker run --rm `
  -v "$($PWD.Path):/work" `
  -w /work `
  $IMAGE `
  run `
    --paths ./examples/docs `
    --policy-root ./examples/policy/.docq `
    --pbc quality_gate `
    --out-dir ./reports

# Test Design split B1 на примерах
docker run --rm `
  -e LLMOPS_API_KEY="$env:LLMOPS_API_KEY" `
  -v "$($PWD.Path):/work" `
  -w /work `
  $IMAGE `
  test-design `
    --mode split `
    --split-by doc_type `
    --feature "./examples/docs/features/installment-availability-check.md" `
    --bundle auto `
    --paths ./examples/docs `
    --policy-root ./examples/policy/.docq `
    --pbc test_design `
    --out-dir ./reports `
    --doc-types feature,api,algorithm,service `
    --generators-map "feature=test_design_e2e_v1,api=test_design_api_v1,algorithm=test_design_algorithm_v1,service=test_design_service_v1" `
    --include-negative `
    --include-edge `
    --emit-plan
```

---

## Что такое PBC

**PBC (Policy Bundle / Policy Content Bundle)** — это пакет политики внутри `.docq`, который содержит только контент:
- шаблоны (templates) для QG
- валидаторы (validators) для QG
- генераторы (generators) для test-design
- (в будущем) профили codegen/mockgen и т.п.

Engine читает PBC через `--policy-root` и `--pbc`.

Поддерживаются 2 раскладки:

### New layout (рекомендуется)
```
.docq/
  config.yml
  pbc/
    quality_gate/
      templates/
      validators/
    test_design/
      generators/
```

### Legacy layout
```
.docq/
  config.yml
  templates/
  validators/
  generators/
```

Подробнее: **docs/POLICY.md**.
