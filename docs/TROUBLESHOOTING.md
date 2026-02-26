# Troubleshooting

## 1) `No markdown files found`
Причины:
- `--paths` указывает на несуществующий каталог
- в каталоге нет `*.md` (например, только `*.MD`)
- запуск из другой папки (не та смонтирована в `/work`)

Проверка внутри контейнера:
```powershell
docker run --rm -v "$($PWD.Path):/work" -w /work <IMAGE> sh -lc "ls -la; find . -maxdepth 4 -type f -name '*.md' | head"
```

---

## 2) Docker не видит Engine (`//./pipe/dockerDesktopLinuxEngine`)
Docker Desktop не запущен / не тот context. Проверь:
```powershell
docker version
docker context ls
```

---

## 3) `TLS handshake timeout` при `docker build` (DockerHub)
Классика корпоративной сети: Docker Engine не может сходить в DockerHub.
Решения:
- proxy cache в корпоративном registry
- `docker save`/`docker load` базового образа
- настроить proxy в Docker Desktop

---

## 4) `Temporary failure in name resolution` (DNS внутри контейнера)
Контейнер не резолвит hostname LLM gateway.
Решения:
- `docker run --dns <corp_dns>` (или настроить DNS в Docker Desktop)
- `--add-host host:ip` как временный костыль

---

## 5) `ReadTimeout` при вызове LLM
Увеличить:
- `llm.timeout_s` (в config.yml)
И уменьшить:
- `llm.max_doc_chars` / `--max-input-chars` в split-mode
- `llm.max_tokens`

---

## 6) “модель вернула схему” / “unbalanced braces”
Движок лечит это через:
- JSON mode (`response_format=json_object` если поддерживается)
- repair + дозакрытие скобок
Но если всё равно часто — уменьшайте output:
- `--max-scenarios` (split)
- `llm.max_tokens`

