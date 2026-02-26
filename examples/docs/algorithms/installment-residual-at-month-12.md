---
doc_type: algorithm
owner: lena.vika@example.com
creation_date: '2026-02-20'
task: EOFFR-TEST-0001
tags:
- eoffr
- installment
- algorithm
- annuity
- residual
id: ALG-EOFFR-0001
title: Residual at month 12 calculation
---

# Алгоритм: проверка доступности рассрочки по остатку тела на 12-й месяц

## Входные данные (строго разделяем)

### 1) Контекст проверки
Из `context.parameters[key/value]`:
- `checkTotalPrice` — стоимость чека
- `smartphonePrice` — стоимость смартфона
- `productSegmentId` — сегмент смартфона

### 2) Параметры проверяемой рассрочки
Из `service.parameters[code/value]`:
- `bankInstallmentPlanDuration` (months)
- `retailDiscount` (%)
- `bankPercent` (% APR)
- `bankCreditId` (optional, не влияет на расчёт)

### 3) Границы residual% по сегменту (stage 1)
По `productSegmentId` получаем:
- `minResidualPercent?`
- `maxResidualPercent`

Источник: конфигурация сервиса (см. [`../services/eoffr-installment-eligibility-service.md`](../services/eoffr-installment-eligibility-service.md)).

## Выход
- `availabilityForCustomer: boolean`
- если `false`: `unavailabilityReason { code, message }`

## Валидации входа (минимум)
- нет `checkTotalPrice` / `smartphonePrice` / `productSegmentId` → `MISSING_REQUIRED_CONTEXT`
- нет обязательных параметров рассрочки → `INVALID_INPUT`
- `smartphonePrice <= 0` или `checkTotalPrice <= 0` → `INVALID_INPUT`
- `retailDiscount < 0` или `retailDiscount > 100` → `INVALID_INPUT`
- `bankPercent < 0` → `INVALID_INPUT`
- сегмент не найден в конфиге → `INVALID_INPUT` ("Segment bounds not configured")
- конфиг недоступен → `TEMPORARY_UNAVAILABLE`

## Расчёт (аннуитет)

Обозначения:
- `principal` — финансируемая сумма
- `n` — срок в месяцах
- `k` — месяц, на который берём остаток (12-й или меньше, если срок < 12)
- `r` — месячная ставка

Шаги:
1) `principal = checkTotalPrice * (1 - retailDiscount/100)`
2) `n = bankInstallmentPlanDuration`
3) `k = min(12, n)`
4) `r = (bankPercent/100)/12`

Остаток тела после `k` платежей:

- если `r == 0`:
  - `residual = principal * (1 - k/n)`
- иначе:
  - `residual = principal * (((1+r)^n - (1+r)^k) / ((1+r)^n - 1))`

Доля остатка относительно стоимости смартфона:
- `residualPercent = residual / smartphonePrice * 100`

## Сравнение с границами
- если `min` задан: `min <= residualPercent <= max`
- иначе: `residualPercent <= max`

Если не попало:
- `availabilityForCustomer=false`
- `code=NOT_ELIGIBLE`
- `message="Residual percent out of allowed range"`

## Округление
ASSUMPTION:
- деньги: decimal, округление до 2 знаков на финальных денежных значениях
- проценты: decimal, сравнение с точностью до 4 знаков

## Связанные документы
- API: [`../api/installment-availability-batch-only.md`](../api/installment-availability-batch-only.md)
- Service: [`../services/eoffr-installment-eligibility-service.md`](../services/eoffr-installment-eligibility-service.md)

## TODO
- Зафиксировать rounding mode (HALF_UP/HALF_EVEN).
- Зафиксировать денежные единицы (рубли/копейки vs minor units).
