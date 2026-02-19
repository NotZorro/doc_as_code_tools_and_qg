# doc-quality (Engine)

Инженерный движок для **Doc Quality Gate**.

- **Engine** = этот репозиторий (Python + Docker).
- **Policy** = в репо с документацией, ветка `qg`, папка `.docq/`:
  - `.docq/templates/*.yaml` (шаблоны документов)
  - `.docq/validators/*` (LLM-валидаторы: schema + prompts как файлы)
  - `.docq/config.yml` (LLM-настройки)

Идея простая: аналитики правят **policy**, CI гоняет **engine**. Магии, кроме обычной человеческой, нет.

---

## Что делает `doc-quality run`

1) читает Markdown, парсит YAML frontmatter  
2) режет документ на секции по markdown headings  
3) выбирает `doc_type`:
- если `doc_type` задан в frontmatter и есть шаблон
- иначе авто-детект по совпадению заголовков с шаблонами  
4) rules-based проверки:
- обязательные meta поля
- обязательные секции
- `min_chars`, `forbid_regex`, `must_have_any_regex`
- грубая проверка порядка секций (`order`)  
5) (опционально) LLM-валидаторы секций (строго JSON по schema)  
6) пишет отчёты:
- `<file>.report.json` на каждый файл (в папке `reports/` зеркалим структуру)
- `reports/summary.json`  
7) выставляет exit code:
- `2` если есть blocker
- `1` если `--fail-on-warn` и есть warning
- `0` если чисто

---

## Быстрый старт (локально, без Docker)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e .

doc-quality run --paths docs --out-dir reports
```

---

## Быстрый старт (Docker)

Сборка:

```bash
docker build -t doc-quality:dev .
```

Запуск (проверка docs/ в текущей папке):

```bash
docker run --rm -v "$PWD:/work" -w /work doc-quality:dev \
  run --paths docs --out-dir reports --no-llm
```

---

## Policy: структура файлов

Ожидаем, что в репозитории с доками есть:

```
.docq/
  config.yml
  templates/
    feature_spec.yaml
  validators/
    business_context_v1/
      validator.yaml
      schema.json
      prompt.system.tmpl
      prompt.user.tmpl
    nfr_v1/
      ...
```

Пути можно переопределить флагами `--templates-dir`, `--validators-dir`, `--config`.

### Как шаблон ссылается на валидатор

В `templates/*.yaml` у секции можно указать:

```yaml
sections:
  - key: business_context
    titles: ["Business context", "Контекст"]
    required: true
    rules:
      min_chars: 200
    validators: [business_context_v1]
```

Добавление нового валидатора = добавление папки в `.docq/validators/`.
CORE (engine) менять не нужно.

---

## LLM: выбор модели аналитиками (без изменения кода)

В `.docq/config.yml`:

```yaml
llm:
  enabled: true
  base_url: https://api.openai.com/v1         # или ваш OpenAI-compat endpoint
  model: gpt-4o-mini                          # или внутренняя модель
  timeout_s: 60
  temperature: 0.0
  max_tokens: 1200
  max_doc_chars: 20000
  max_section_chars: 8000
  # allowed_models: ["gpt-4o-mini", "gpt-4.1-mini"]   # опционально: allow-list
```

Ключ **только** через env:

- `LLMOPS_API_KEY` (обязателен для LLM-части)

Приоритеты:
- `LLM_MODEL` (env) перекрывает `llm.model`
- `LLMOPS_BASE_URL` (env) перекрывает `llm.base_url`
- `LLMOPS_API_KEY` берём только из env

Пример:

```bash
export LLMOPS_API_KEY="***"
export LLM_MODEL="gpt-4o-mini"
export LLMOPS_BASE_URL="https://api.openai.com/v1"

doc-quality run --paths docs --out-dir reports
```

Если не хотите LLM вообще: `--no-llm`.

---

## Быстрая проверка одного раздела (для аналитиков)

Когда правите документ и хотите сразу получить подсказки по конкретному разделу:

```bash
doc-quality section --file docs/Feature-0001.md --section business_context --pretty
```

`--section` принимает либо `key` секции из шаблона, либо заголовок (title).
Если хотите запустить конкретный валидатор вручную:

```bash
doc-quality section --file docs/Feature-0001.md --section business_context --validator business_context_v1 --pretty
```

---

## GitLab CI: как подтянуть policy из ветки `qg` (пример)

Локально это тоже можно повторить, если надо:

```bash
git fetch origin qg

mkdir -p .docq/templates
git show origin/qg:.docq/config.yml > .docq/config.yml
# templates целиком
git ls-tree -r --name-only origin/qg .docq/templates | while read -r f; do
  mkdir -p "$(dirname "$f")"
  git show "origin/qg:$f" > "$f"
done
```

---

## Формат frontmatter (минимум)

```yaml
---
id: Feature-0001
title: Промо наследование стратегии
doc_type: feature
owner: someone@company.ru
status: draft
last_reviewed: 2026-02-19
tags: [service, api]
---
```

Даты можно писать как `YYYY-MM-DD` (PyYAML иногда парсит в `date`, движок это нормально сериализует в JSON).

---

## Troubleshooting

- LLM отвечает не JSON: движок делает до 2 попыток ремонта.
- LLM внезапно пишет CJK/китайский: включён ремонт "перепиши строго на русском и верни JSON".

(Это сраная магия, но работает.)

