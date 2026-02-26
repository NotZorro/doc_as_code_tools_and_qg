---
doc_type: api
owner: lena.vika@example.com
creation_date: '2026-02-20'
task: EOFFR-TEST-0001
tags:
- eoffr
- installment
- availability
- api
- rest
- batch-only
- openapi
id: API-EOFFR-0001
title: Installment availability (batch-only) API
---

# API: Проверка доступности рассрочки (batch-only)

## Endpoint
- `POST /v1/availability/batch`
- Content-Type: `application/json`

OpenAPI схема: [`../../openapi/service-availability-openapi.yaml`](../../openapi/service-availability-openapi.yaml)

## Формат
Batch-only:
- тело запроса **всегда** массив `customerBatchItem[]` (может содержать 1 элемент)
- тело ответа **всегда** массив `customerBatchResult[]`

## Request

### customerBatchItem
Обязательные поля:
- `batchItemAlias: string`
- `items: serviceAction[]`

Опционально:
- `customer`
- `context`

### context.parameters (разделение данных)
`context.parameters[]` содержит параметры **контекста проверки** (не параметры рассрочки).

Обязательные ключи для проверки рассрочки:
- `checkTotalPrice` — стоимость чека (денежное значение)
- `smartphonePrice` — стоимость смартфона в составе чека (денежное значение)
- `productSegmentId` — идентификатор сегмента смартфона (строка)

ASSUMPTION:
- деньги передаются строкой decimal (пример: `"99990.00"`)

### serviceAction
- `alias: string` — корреляция результата
- `action: string` — тип действия (по каноническому контракту, например `ADD/UPDATE/DELETE`)
- `service`:
  - `serviceSpecification.id: string` — идентификатор сервиса, согласованный на онбординге
  - `parameters[]` — параметры проверяемого сервиса (code/value, значения строками)

### service.parameters (параметры рассрочки)
Ожидаемые `code`:
- `bankInstallmentPlanDuration` (int, months)
- `retailDiscount` (float, %)
- `bankPercent` (float, % APR)
- `bankCreditId` (optional)

Пример фрагмента `parameters`:
```json
[
  {"code": "bankInstallmentPlanDuration", "value": "16"},
  {"code": "retailDiscount", "value": "12.17"},
  {"code": "bankPercent", "value": "18.83"},
  {"code": "bankCreditId", "value": "optional-credit-program-id"}
]
```

## Response

### customerBatchResult
Обязательные поля:
- `batchItemAlias: string`
- `results: availabilityCheckResult[]`

### availabilityCheckResult
- `alias: string` — тот же alias из запроса
- `availabilityForCustomer: boolean`
- `unavailabilityReason?: { code: string, message: string }` — только если `availabilityForCustomer=false`

## Коды причин недоступности (unavailabilityReason.code)
- `MISSING_REQUIRED_CONTEXT` — отсутствуют обязательные параметры контекста
- `INVALID_INPUT` — некорректные значения параметров/отсутствует конфиг сегмента
- `NOT_ELIGIBLE` — расчёт выполнен, residual% вне границ
- `TEMPORARY_UNAVAILABLE` — сервис временно не может выполнить проверку (например, конфиг не загружен)
- `TECHNICAL_ERROR` — внутренняя ошибка

## HTTP статусы
- `200` — запрос обработан (включая бизнес-недоступность)
- `500` — невозможно обработать запрос целиком

## Пример запроса (batch из 1 элемента)
```json
[
  {
    "batchItemAlias": "item-001",
    "context": {
      "parameters": [
        {"key": "checkTotalPrice", "value": "100000.00"},
        {"key": "smartphonePrice", "value": "80000.00"},
        {"key": "productSegmentId", "value": "SEGMENT_A"}
      ]
    },
    "items": [
      {
        "alias": "installment-1",
        "action": "ADD",
        "service": {
          "serviceSpecification": {"id": "installment-plan"},
          "parameters": [
            {"code": "bankInstallmentPlanDuration", "value": "16"},
            {"code": "retailDiscount", "value": "12.17"},
            {"code": "bankPercent", "value": "18.83"}
          ]
        }
      }
    ]
  }
]
```

## Пример ответа (недоступно)
```json
[
  {
    "batchItemAlias": "item-001",
    "results": [
      {
        "alias": "installment-1",
        "availabilityForCustomer": false,
        "unavailabilityReason": {
          "code": "NOT_ELIGIBLE",
          "message": "Residual percent out of allowed range"
        }
      }
    ]
  }
]
```

## Связанные документы
- Service: [`../services/eoffr-installment-eligibility-service.md`](../services/eoffr-installment-eligibility-service.md)
- Algorithm: [`../algorithms/installment-residual-at-month-12.md`](../algorithms/installment-residual-at-month-12.md)
