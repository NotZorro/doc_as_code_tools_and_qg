---
doc_type: service
owner: lena.vika@example.com
creation_date: '2026-02-20'
task: EOFFR-TEST-0001
tags:
- eoffr
- installment
- availability
- service-provider
- batch-only
- rest
id: SVC-EOFFR-0001
title: Installment Eligibility Service
---

# EOFFR Installment Eligibility Service

## Назначение
Предоставляет проверку доступности сервиса “Рассрочка” по правилу **остатка тела кредита на 12-й месяц**.

## Как использовать

### Endpoint
- `POST /v1/availability/batch`
- Формат: batch-only (тело запроса и ответа всегда массивы)

### Контракт
- Описание API: [`../api/installment-availability-batch-only.md`](../api/installment-availability-batch-only.md)
- OpenAPI схема: [`../../openapi/service-availability-openapi.yaml`](../../openapi/service-availability-openapi.yaml)

### Входные данные (вкратце)
1) Контекст проверки (`context.parameters[]`):
- `checkTotalPrice`
- `smartphonePrice`
- `productSegmentId`

2) Параметры проверяемой рассрочки (`service.parameters[]`):
- `bankInstallmentPlanDuration`
- `retailDiscount`
- `bankPercent`
- `bankCreditId` (optional)

### Результат
Для каждого проверяемого сервиса:
- `availabilityForCustomer=true|false`
- если `false`: `unavailabilityReason { code, message }`

Список кодов и семантика: см. API doc.

### Авторизация/доступ
- Base URL: TODO
- Auth: TODO (mTLS/JWT/другое)
- Rate limits: TODO
- Client timeout recommendation: TODO

## Алгоритм
Алгоритм расчёта зафиксирован в документе:
- [`../algorithms/installment-residual-at-month-12.md`](../algorithms/installment-residual-at-month-12.md)

## Конфигурация: границы residual% по сегменту (stage 1)
Границы определяются по `productSegmentId` из конфигурации сервиса.

### Файл конфига
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

### Поведение при проблемах
- Если в контексте нет `productSegmentId` → `MISSING_REQUIRED_CONTEXT`
- Если `productSegmentId` есть, но сегмента нет в конфиге → `INVALID_INPUT` (message: "Segment bounds not configured")
- Если конфиг не читается/невалиден → `TEMPORARY_UNAVAILABLE` (policy TODO: fail-fast vs degraded)

Решение “границы в конфиге”: [`../adr/ADR-EOFFR-0002-segment-bounds-config-v1.md`](../adr/ADR-EOFFR-0002-segment-bounds-config-v1.md)

## Observability (минимум)
- `availability_requests_total{result}`
- `availability_unavailable_total{reason_code}`
- `availability_latency_ms` (p50/p95)
- `config_load_failures_total`
- `segment_bounds_missing_total`

## Эксплуатация
Playbook: [`../playbooks/eoffr-installment-eligibility-service.md`](../playbooks/eoffr-installment-eligibility-service.md)

## Связанные документы
- Feature: [`../features/installment-availability-check.md`](../features/installment-availability-check.md)
- API: [`../api/installment-availability-batch-only.md`](../api/installment-availability-batch-only.md)
- Algorithm: [`../algorithms/installment-residual-at-month-12.md`](../algorithms/installment-residual-at-month-12.md)
- ADR: [`../adr/ADR-EOFFR-0002-segment-bounds-config-v1.md`](../adr/ADR-EOFFR-0002-segment-bounds-config-v1.md)

## TODO
- Зафиксировать политику конфигурации (fail-fast vs degraded).
- Зафиксировать rounding mode и формат денег.
- Зафиксировать требования по ограничениям (max batch size, timeouts).
