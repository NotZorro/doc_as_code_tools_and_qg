# Разработка (DEVELOPMENT)

## 1) Архитектура (куда смотреть в коде)

Ключевые части движка:

- `doc_quality/cli.py`  
  CLI entrypoint: поднимает argparse и регистрирует capabilities.

- `doc_quality/capabilities/*`  
  Каждая capability = отдельная команда/юнит работы:
  - `quality_gate.py`: `run` и `section`
  - `test_design.py`: `test-design` (single + split B1)
  - `test_codegen.py`: `test-codegen`
  - `mockgen.py`: `mockgen`
  Реестр: `capabilities/registry.py`

- `doc_quality/engine.py`  
  Ядро Quality Gate: парсинг документов, rules‑checks, вызов валидаторов, запись отчётов.

- `doc_quality/policy.py`  
  Загрузка templates и автодетект `doc_type`.

- `doc_quality/pbc.py`  
  Резолв путей policy: new layout `pbc/<pbc>/...` и legacy layout.

- `doc_quality/validators.py` / `doc_quality/generators.py`  
  Загрузка policy-defined LLM specs.

- `doc_quality/llm/*`  
  OpenAI‑compatible клиент + JSON‑mode (`llm_json`) с repair и защитами.

- `doc_quality/test_design/*`  
  Split-mode B1: планирование, merge, coverage.

- `doc_quality/renderers/*`  
  Детерминированные рендеры (json/md/text) для артефактов.

---

## 2) Как добавить новую capability

1) Создать файл `doc_quality/capabilities/my_cap.py` и класс с:
   - `name = "my_cap"`
   - `register(subparsers)` — добавить подкоманду
   - `run(args, ctx)` — выполнить

2) Зарегистрировать в `doc_quality/capabilities/registry.py`:
```python
from .my_cap import MyCap
...
return [..., MyCap()]
```

3) Добавить тесты в `tests/` (желательно).

---

## 3) Как добавить новый renderer

1) Создать файл `doc_quality/renderers/my_renderer.py`
2) Реализовать `name` и `render(data, ctx) -> str`
3) Добавить в `doc_quality/renderers/registry.py` в `_BUILTINS`

---

## 4) Как добавить новый валидатор/генератор (без правки кода)
Это не 개발, это policy:
- новый валидатор: `.docq/.../validators/<id>/...`
- новый генератор: `.docq/.../generators/<id>/...`

Код менять не надо.

---

## 5) Тесты

```bash
pytest -q
```

Для запуска в Docker можно собрать отдельный target (если добавите), но обычно проще локально.

---

## 6) Релиз / версии образов

Рекомендуемый подход:
- локально: `docker build -t docq:dev .`
- CI: пуш в registry с тегом по pipeline/tag
- policy (PBC) версионируется в репозитории с доками (ветка/тег).

