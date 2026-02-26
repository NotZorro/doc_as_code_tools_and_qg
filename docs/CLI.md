# CLI справочник (команды и параметры)

Ниже — точное описание команд CLI, их параметров и эффектов.

## Команда: `run` (Quality Gate)

```text
doc-quality run [options]
```

Параметры:
- `--paths <p1> <p2> ...`  
  Список файлов/директорий. Движок ищет `*.md` внутри директорий рекурсивно.
- `--paths-file <file>`  
  Файл со списком путей (по одному на строку). Самый надёжный способ для путей с пробелами.
- `--policy-root <dir>`  
  Корень policy (`.docq`). По умолчанию `.docq`.
- `--pbc <name>`  
  Имя PBC. По умолчанию `quality_gate`.
- `--templates-dir <dir>`  
  Явный overrides для templates (обходит `policy-root/pbc`).
- `--validators-dir <dir>`  
  Явный overrides для validators.
- `--config <file>`  
  Явный overrides для config.yml.
- `--layout flat|mirror`  
  - `flat`: всё в одной папке, имена с префиксом `qg.*` (по умолчанию).  
  - `mirror`: зеркалит структуру путей документов.
- `--out-dir <dir>`  
  Куда писать отчёты. По умолчанию `reports`.
- `--no-llm`  
  Отключить LLM‑валидаторы (останутся rules‑based проверки).
- `--fail-on-warn`  
  Возвращать exit code `1`, если есть warnings (без blockers).

Выходы (layout=flat):
- `qg.summary.json`
- `qg.<slug>.report.json` на каждый файл

Exit codes:
- `0` — ок
- `1` — warnings (если `--fail-on-warn`)
- `2` — blockers

---

## Команда: `section` (точечная проверка секции)

```text
doc-quality section --file <md> --section <selector> [options]
```

Параметры:
- `--file <path>` — markdown файл.
- `--section <selector>` — ключ секции из template (`key`) **или** заголовок секции.
- `--validator <id>` — запускать только один валидатор (override).
- `--policy-root/--pbc/--templates-dir/--validators-dir/--config` — как в `run`.
- `--no-llm` — только rules‑checks.
- `--json` — печатать только JSON.
- `--pretty` — pretty JSON.

---

## Команда: `test-design` (генерация test suite)

```text
doc-quality test-design --feature <feature.md> [options]
```

Базовые параметры:
- `--feature <path>` — главный feature документ.
- `--paths ...` / `--paths-file ...` — где искать связанные документы (bundle).
- `--bundle none|auto` — как строить bundle.
- `--policy-root <dir>` — корень policy.
- `--pbc <name>` — имя PBC для генераторов (по умолчанию `test_design`).
- `--generators-dir <dir>` — overrides для генераторов.
- `--generator <id>` — дефолтный генератор (по умолчанию `test_design_v1`).
- `--config <file>` — overrides config.yml.
- `--out-dir <dir>` — куда писать артефакты.
- `--result-id <id>` — идентификатор для имён выходных файлов (по умолчанию берётся из feature.id).
- `--layout flat|grouped`  
  - `flat`: всё в `--out-dir`, префиксы `td.*` (по умолчанию)  
  - `grouped`: раскладка в `test_design/<...>` как “папки по смыслу”
- `--no-llm` — выключить LLM (для test-design это фактически ошибка, генерации не будет)

Опции генерации:
- `--include-negative`
- `--include-edge`
- `--include-nfr`

Выходы:
- `--emit-json` — писать `*.test_suite.json`
- `--emit-md` — писать `*.test_suite.md`
Если ни один не указан — движок пишет оба.

Split mode (B1):
- `--mode single|split` (по умолчанию `single`)
- `--split-by doc_type` (сейчас только это)
- `--doc-types <csv>` — allow‑list групп (doc_type)
- `--generators-map <csv>` — маппинг `group=generator_id`
- `--max-input-chars <int>` — лимит input на один LLM вызов
- `--max-scenarios <int>` — целевое число сценариев на part
- `--emit-plan` — писать план выполнения
- `--keep-fragments` — писать fragments по частям
- `--no-coverage` — отключить coverage index

Имена выходов (layout=flat):
- plan: `td.<result_id>.plan.json`
- fragments: `td.<group>.<result_id>.partNN.fragment.json`
- suites: `td.<group>.<result_id>.test_suite.(json|md)`
- coverage: `td.<result_id>.coverage.(json|md)`

---

## Команда: `test-codegen` (pytest skeleton)

```text
doc-quality test-codegen --test-suite <file.json> [options]
```

Параметры:
- `--test-suite` — путь к `*.test_suite.json`
- `--out-dir` — куда писать (по умолчанию `generated`)
- `--framework pytest` — пока только pytest

Выход:
- `<out-dir>/tests/test_<feature>.py`

---

## Команда: `mockgen` (wiremock placeholders)

```text
doc-quality mockgen --test-suite <file.json> [options]
```

Параметры:
- `--test-suite` — путь к `*.test_suite.json`
- `--out-dir` — куда писать (по умолчанию `generated`)
- `--format wiremock` — пока wiremock placeholders

Выход:
- `<out-dir>/mocks/<feature>/README.md`
- `<out-dir>/mocks/<feature>/wiremock_mappings/*.json`

