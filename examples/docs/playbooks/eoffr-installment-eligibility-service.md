---
doc_type: playbook
owner: lena.vika@example.com
creation_date: '2026-02-20'
task: EOFFR-TEST-0001
tags:
- eoffr
- installment
- availability
- playbook
- incidents
- config
id: PB-EOFFR-0001
title: 'Runbook: installment eligibility service'
---

# Playbook: Installment Eligibility Service

## 0) Что делает сервис
Принимает batch-only запросы проверки доступности рассрочки и возвращает по каждому сервису:
- `availabilityForCustomer=true|false`
- при `false`: `unavailabilityReason` (code + message)

Контракт и примеры: [`../api/installment-availability-batch-only.md`](../api/installment-availability-batch-only.md)

## 1) Конфиг сегментных границ: где лежит и как валидировать

### Где лежит
ASSUMPTION:
- `config/installment-segment-bounds.yaml`

Reference:
- пример: [`../../config/installment-segment-bounds.example.yaml`](../../config/installment-segment-bounds.example.yaml)
- схема: [`../../config/installment-segment-bounds.schema.json`](../../config/installment-segment-bounds.schema.json)
- валидатор: [`../../tools/validate_segment_bounds.py`](../../tools/validate_segment_bounds.py)

### Правила
- `maxResidualPercent` обязателен для каждого сегмента
- `minResidualPercent` опционален
- `0 <= min <= max <= 100`

### Проверки в CI (рекомендуется)
1) YAML синтаксис (парсинг)
2) Проверка схемы (JSON Schema)
3) Бизнес-правила (min<=max, диапазон 0..100)

Пример запуска валидатора:
```bash
python tools/validate_segment_bounds.py config/installment-segment-bounds.yaml
```

## 2) Метрики и алерты

### Метрики
- `availability_requests_total{result}`
- `availability_unavailable_total{reason_code}`
- `availability_latency_ms_p95`
- `segment_bounds_missing_total`
- `config_load_failures_total`

### Алерты (пример)
- `5xx_rate > 1%` за 5 минут
- доля `TEMPORARY_UNAVAILABLE` > X% за 10 минут (проблемы конфига/старта)
- доля `INVALID_INPUT` > Y% за 15 минут (сломали вход/забыли сегмент)

## 3) Типовые инциденты

### I-1: Массовый INVALID_INPUT из-за сегментов
**Симптомы**
- всплеск `INVALID_INPUT`
- сообщения "Segment bounds not configured"

**Диагностика**
- проверить наличие `productSegmentId` во входе
- проверить актуальность `config/installment-segment-bounds.yaml`
- проверить, что сегмент действительно присутствует

**Решение**
- добавить сегмент в конфиг и применить обновление (по принятой политике)
- при ошибке у потребителя: вернуть им перечень обязательных ключей контекста

### I-2: TEMPORARY_UNAVAILABLE после релиза/рестарта
**Симптомы**
- причина `TEMPORARY_UNAVAILABLE`
- ошибки чтения/парсинга конфига

**Диагностика**
- логи загрузки конфигурации
- прогнать валидатор на текущем файле

**Решение**
- откат конфига/релиза
- добавить обязательную preflight-валидацию в CI, если отсутствует

### I-3: Расхождение расчётов
**Причины**
- разные rounding mode / формат денег
- неверная трактовка `retailDiscount` или `bankPercent`
- разные исходные суммы чека/смартфона

**Действия**
- пересчитать по алгоритму: [`../algorithms/installment-residual-at-month-12.md`](../algorithms/installment-residual-at-month-12.md)
- сверить входные значения и правила округления

## 4) Контакты
- Owner: TODO
- On-call: TODO
- Чат: TODO

## Связанные документы
- Service: [`../services/eoffr-installment-eligibility-service.md`](../services/eoffr-installment-eligibility-service.md)
- ADR: [`../adr/ADR-EOFFR-0002-segment-bounds-config-v1.md`](../adr/ADR-EOFFR-0002-segment-bounds-config-v1.md)
