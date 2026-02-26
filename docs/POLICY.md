# Policy / PBC (шаблоны, валидаторы, генераторы, промпты)

## 1) Что такое policy и где она живёт
Policy — это **контент**, который настраивают аналитики/команда без правки engine-кода.

В репозитории с доками ожидается папка `.docq/`.

### Рекомендуемая структура (new layout)
```
.docq/
  config.yml
  pbc/
    quality_gate/
      templates/
        *.yaml
      validators/
        <validator_id>/
          validator.yaml
          schema.json
          prompt.system.tmpl
          prompt.user.tmpl
    test_design/
      generators/
        <generator_id>/
          generator.yaml
          schema.json
          prompt.system.tmpl
          prompt.user.tmpl
```

### Legacy структура (поддерживается)
```
.docq/
  config.yml
  templates/
  validators/
  generators/
```

Engine выбирает PBC через:
- `--policy-root ./.docq`
- `--pbc quality_gate | test_design`

Если `--templates-dir/--validators-dir/--generators-dir/--config` указаны явно — они имеют приоритет.

---

## 2) config.yml (LLM настройки)

`config.yml` содержит настройки LLM (по умолчанию — OpenAI API):

```yaml
llm:
  enabled: true
  base_url: https://api.openai.com/v1
  model: gpt-4o-mini
  timeout_s: 300
  temperature: 0.0
  max_tokens: 1200
  max_doc_chars: 20000
  max_section_chars: 8000
  # allowed_models: [gpt-4o-mini, ...]  # optional allow-list
```

Приоритет настроек:
1) переменные окружения (`LLMOPS_BASE_URL`, `LLM_MODEL`)
2) overrides в конкретном генераторе/валидаторе (см. ниже)
3) `config.yml`

---

## 3) Templates (Quality Gate)

Файл `templates/*.yaml` описывает:
- required meta (frontmatter)
- набор секций (по заголовкам) и rules
- какие LLM‑валидаторы запускать на секции

Пример (из examples):

```yaml
id: feature_spec_v1
doc_type: feature

meta:
  required: [id, title, doc_type, owner, status, last_reviewed]
  optional: [tags, related, reviewers, valid_until]

sections:
  - key: business_context
    titles: ["Контекст бизнес-задачи", "Business context"]
    required: true
    order: 20
    rules:
      min_chars: 200
    validators: [business_context_v1]
```

### Правила секций (`rules`)
Поддерживаются (движок расширяем):
- `min_chars`
- `forbid_regex`
- `must_have_any_regex`

---

## 4) Validators (LLM‑проверки секций)

Структура валидатора:
```
validators/<id>/
  validator.yaml
  schema.json
  prompt.system.tmpl
  prompt.user.tmpl
```

Пример `validator.yaml`:

```yaml
id: business_context_v1
kind: section
input: section_text
schema: schema.json
prompts:
  system: prompt.system.tmpl
  user: prompt.user.tmpl
output:
  max_retries: 2
  anti_cjk_repair: true
# (опционально) llm override:
# llm:
#   model: gpt-4o-mini
#   temperature: 0.0
#   max_tokens: 1200
```

### Как валидатор вызывается
В prompt движок подставляет переменные (через `string.Template`):
- `${schema}` — текст schema.json
- `${doc_meta_json}` — мета (JSON)
- `${doc_text}` — текст документа (может быть обрезан)
- `${section_text}` — текст секции (обрезан `max_section_chars`)
- `${options_json}` — опции
- `${bundle_json}` — bundle (обычно пусто для QG)

---

## 5) Generators (Test Design)

Структура генератора:
```
generators/<id>/
  generator.yaml
  schema.json
  prompt.system.tmpl
  prompt.user.tmpl
```

Пример `generator.yaml`:

```yaml
id: test_design_v1
kind: document
input: doc_text
schema: schema.json
prompts:
  system: prompt.system.tmpl
  user: prompt.user.tmpl
output:
  max_retries: 2
  anti_cjk_repair: true
llm:
  model: gpt-4o-mini
  temperature: 0.1
  max_tokens: 1800
  # base_url: https://api.openai.com/v1
  # timeout_s: 300
```

### Split-mode и generators-map
В split‑режиме можно назначить разные генераторы на разные группы `doc_type`:

```
--generators-map "feature=test_design_e2e_v1,api=test_design_api_v1,algorithm=test_design_algorithm_v1,service=test_design_service_v1"
```

Если для группы нет маппинга — используется `--generator` (дефолт `test_design_v1`).

---

## 6) Требования к метаданным документов (для bundle auto)
Для корректного bundle auto вам нужны:
- `doc_type` (строка: feature/api/algorithm/service/…)
- `task` (одинаковый для всей фичи, напр. `EOFFR-1234`)
- `id` и `title` желательно (иначе будет fallback)

Именно по `task` движок собирает документы одной фичи.

