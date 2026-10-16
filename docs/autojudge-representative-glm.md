# AutoJudge: representative GLM evaluation

## Цель

Проверить, сохраняется ли эффект, обнаруженный на HaluMem case 001,
на нескольких разных типах временных ошибок.

Для оценки использовался фиксированный набор AutoJudge-оценщиков
и одна модель `glm-5.3-flash`.

## Выборка

Выбрано 5 кейсов HaluMem Memory Conflict:

- `001` — transition/retrospective + evidence after question time;
- `007` — state-at-time + evidence after question time;
- `009` — transition/retrospective + expired evidence;
- `010` — expired evidence + zero-length interval;
- `027` — state-at-time + dated event after question time.

Для каждого кейса сравнивались 5 retrieval policies:

- `before_aware`
- `flat_bm25`
- `query_aware`
- `strict_temporal`
- `transition_aware`

Всего: 5 × 5 = 25 оценок.

## Основной результат

| Policy | Supports answer |
|---|---:|
| `flat_bm25` | 5/5 |
| `query_aware` | 3/5 |
| `before_aware` | 2/5 |
| `strict_temporal` | 2/5 |
| `transition_aware` | 2/5 |

`flat_bm25` чаще всего сохраняет достаточно evidence для ответа,
но иногда вместе с нужными фактами извлекает конфликтующие версии.

`query_aware` улучшает результат в отдельных retrospective-кейсах,
но не является универсальным решением.

`strict_temporal` часто сохраняет временно согласованный контекст,
но теряет evidence, необходимое для ответа.

## Наблюдения по кейсам

### Case 001

Исходная гипотеза подтверждается:
`strict_temporal` теряет необходимый поздний факт,
а `query_aware` извлекает релевантный out-of-slice факт
и позволяет ответить без дополнительного конфликта.

### Case 007

`query_aware` уже не помогает.
Достаточный контекст получил только `flat_bm25`.

Это показывает, что одного query-aware правила недостаточно.

### Case 009

Практически все политики дают достаточно evidence для ответа.
Значит, наличие expired evidence само по себе не означает,
что строгая временная фильтрация обязательно ухудшит результат.

### Case 010

Все политики позволяют ответить.
AutoJudge в основном определяет различия между фактами
как `temporal_update`, а не как `true_conflict`.

Это полезный пример различия между изменением состояния
и реальным противоречием.

### Case 027

`flat_bm25` получает нужный поздний факт и поддерживает ответ,
а `query_aware`, `strict_temporal`, `before_aware`
и `transition_aware` необходимое evidence не сохраняют.

## Промежуточный вывод

Эксперимент подтверждает, что строгая point-in-time фильтрация
может удалять информацию, необходимую для ретроспективного рассуждения.

Однако простое разрешение out-of-slice evidence
для определённого типа вопросов недостаточно.

Следующая гипотеза:
решение о включении out-of-slice evidence должно учитывать
не только временное направление вопроса,
но и семантическую роль конкретного факта.

Результат пока является небольшой qualitative validation
на пяти специально выбранных кейсах, а не итоговой оценкой
на всём HaluMem.
