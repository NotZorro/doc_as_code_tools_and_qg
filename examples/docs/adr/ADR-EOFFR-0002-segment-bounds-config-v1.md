---
doc_type: adr
owner: lena.vika@example.com
creation_date: '2026-02-20'
task: EOFFR-TEST-0001
tags:
- eoffr
- installment
- adr
- segment
- bounds
- config
- tech-debt
id: ADR-EOFFR-0002
title: Segment bounds configuration v1
---

# ADR-EOFFR-0002: Границы residual% по сегменту храним в конфиге (stage 1), сервис управления откладываем

## Status
Accepted

## Context
Границы residual% (min/max) зависят от продуктового сегмента смартфона (`productSegmentId`).
Планировалось сделать отдельное управление сегментами/границами, но на этапе 1 требуется быстрый запуск.

## Decision
1) На этапе 1 `minResidualPercent/maxResidualPercent` берём из конфигурации по `productSegmentId`.
2) В availability API границы не передаём.
3) Сервис управления сегментами/границами не реализуем на этапе 1.
4) Вводим схему конфига и обязательную валидацию (preflight/CI).

## Consequences
Плюсы:
- быстрее запуск и меньше интеграций
- минимум зависимостей в рантайме

Минусы:
- управление через конфиги/релизы
- риск “не добавили сегмент” → рост `INVALID_INPUT`
- нужен контроль качества конфигов (валидатор, тесты)

## Tech debt
Сделать управляемый источник правды для границ:
- CRUD через admin API
- аудит изменений (кто/когда/почему)
- безопасная доставка в рантайм (кэш/TTL/версионирование)

## Failure modes
- нет `productSegmentId` → `MISSING_REQUIRED_CONTEXT`
- сегмента нет в конфиге → `INVALID_INPUT` ("Segment bounds not configured")
- конфиг не загрузился/невалиден → `TEMPORARY_UNAVAILABLE` или fail-fast (policy TODO)

## Links
- Algorithm: [`../algorithms/installment-residual-at-month-12.md`](../algorithms/installment-residual-at-month-12.md)
- Service: [`../services/eoffr-installment-eligibility-service.md`](../services/eoffr-installment-eligibility-service.md)
- API: [`../api/installment-availability-batch-only.md`](../api/installment-availability-batch-only.md)
