---
doc_type: feature
owner: lena.vika@example.com
creation_date: '2026-02-20'
task: EOFFR-TEST-0001
tags:
- eoffr
- offering
- installment
- availability
- residual-value
id: Feature-EOFFR-0001
title: Installment availability check
---

# Проверка доступности рассрочки по остатку тела на 12-й месяц

## Цель
Сделать единое правило применимости банковской рассрочки: рассрочка **доступна** клиенту только если **остаток тела кредита на 12-й месяц** укладывается в допустимые границы (в процентах от стоимости смартфона).

## Scope

### In scope
- Проверка доступности **конкретной** рассрочки по входным данным:
  - контекст проверки: стоимость чека и стоимость смартфона (+ сегмент смартфона),
  - параметры проверяемой рассрочки: ставка, срок, скидка,
  - границы residual% для сегмента смартфона (stage 1: из конфигурации сервиса).
- Результат проверки всегда:
  - `available` / `unavailable`
  - если `unavailable` — причина (`reason code` + сообщение).

### Out of scope
- Выбор “лучшей” рассрочки из набора.
- Любые операции “подключить/зарезервировать/оформить” рассрочку (только проверка).
- Получение/обогащение параметров из витрин/каталогов (принимаем на вход готовыми).
- Выдача наружу диагностик расчёта (остаток/процент) как обязательной части публичного ответа.

## Бизнес-правила
### BR-1. Остаток считаем на 12-й месяц
Остаток тела кредита считается после 12 платежей (или после `min(12, срок)` платежей, если срок меньше 12).

### BR-2. База кредита от чека, процент остатка от смартфона
- Финансируемая сумма считается от **стоимости чека с учётом скидки**.
- Процент остатка для сравнения границ считается как:
  - `residualPercent = residualPrincipal / smartphonePrice * 100`.

### BR-3. Границы зависят от продуктового сегмента
Допустимые границы residual% определяются по `productSegmentId`.

На этапе 1 границы берутся из конфигурации сервиса (см. ADR).

### BR-4. Доступность
Рассрочка доступна, если `residualPercent` попадает в диапазон:
- если min задан: `min <= residualPercent <= max`
- если min отсутствует: `residualPercent <= max`

## Краткое техническое решение
- Разрабатываем сервис проверки доступности рассрочки: [`../services/eoffr-installment-eligibility-service.md`](../services/eoffr-installment-eligibility-service.md)
- Сервис реализует канонический batch-only контракт проверки доступности:
  - описание API: [`../api/installment-availability-batch-only.md`](../api/installment-availability-batch-only.md)
  - OpenAPI схема: [`../../openapi/service-availability-openapi.yaml`](../../openapi/service-availability-openapi.yaml)
- Алгоритм расчёта и сравнения границ зафиксирован в документе:
  - [`../algorithms/installment-residual-at-month-12.md`](../algorithms/installment-residual-at-month-12.md)
- Границы residual% на этапе 1 храним в конфигурации сервиса (а не в отдельном сервисе управления):
  - ADR: [`../adr/ADR-EOFFR-0002-segment-bounds-config-v1.md`](../adr/ADR-EOFFR-0002-segment-bounds-config-v1.md)
  - пример конфига: [`../../config/installment-segment-bounds.example.yaml`](../../config/installment-segment-bounds.example.yaml)
- Эксплуатационное сопровождение:
  - Playbook: [`../playbooks/eoffr-installment-eligibility-service.md`](../playbooks/eoffr-installment-eligibility-service.md)

## Артефакты фичи
- Feature: [`./installment-availability-check.md`](installment-availability-check.md)
- Service: [`../services/eoffr-installment-eligibility-service.md`](../services/eoffr-installment-eligibility-service.md)
- API: [`../api/installment-availability-batch-only.md`](../api/installment-availability-batch-only.md)
- Algorithm: [`../algorithms/installment-residual-at-month-12.md`](../algorithms/installment-residual-at-month-12.md)
- ADR: [`../adr/ADR-EOFFR-0002-segment-bounds-config-v1.md`](../adr/ADR-EOFFR-0002-segment-bounds-config-v1.md)
- Playbook: [`../playbooks/eoffr-installment-eligibility-service.md`](../playbooks/eoffr-installment-eligibility-service.md)
- OpenAPI: [`../../openapi/service-availability-openapi.yaml`](../../openapi/service-availability-openapi.yaml)
- Config (example): [`../../config/installment-segment-bounds.example.yaml`](../../config/installment-segment-bounds.example.yaml)
- Config (schema): [`../../config/installment-segment-bounds.schema.json`](../../config/installment-segment-bounds.schema.json)
- Config validator: [`../../tools/validate_segment_bounds.py`](../../tools/validate_segment_bounds.py)

## Нефункциональные ожидания
- Детерминированность расчёта.
- Денежная математика через decimal с фиксированным округлением.
- Низкая латентность (O(1) на один проверяемый сервис).

## ASSUMPTION
- `retailDiscount` и `bankPercent` заданы в процентах.
- `productSegmentId` приходит в контексте проверки.

## TODO
- Зафиксировать “стоимость чека”: до/после других промо/коэффициентов (кроме `retailDiscount`).
- Зафиксировать правила округления и формат денег (строка decimal vs minor units).
