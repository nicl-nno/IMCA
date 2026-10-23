# AutoJudge: independent vs sequential judges

## Цель

Дополнительно была проверена организация специализированных AutoJudge-проверок.

Задача эксперимента - понять, влияет ли передача промежуточных выводов между judges на итоговую семантическую оценку retrieved context.

Сравнивались два варианта:

1. `independent judges` - каждый специализированный judge независимо анализирует один и тот же retrieved context, после чего результаты объединяет `FINAL_AGGREGATOR`;

2. `sequential judges with shared context` - результаты более ранних специализированных проверок передаются следующим judges и могут использоваться ими как дополнительный контекст.

Важно: `independent` здесь не означает обязательное одновременное выполнение API-запросов. Проверки могут запускаться последовательно по времени, но не используют результаты друг друга.

---

## Judges

В обоих вариантах использовался одинаковый набор:

- `CONSISTENCY_JUDGE`;
- `TEMPORAL_JUDGE`;
- `EVIDENCE_JUDGE`;
- `OUT_OF_SLICE_JUDGE`;
- `FINAL_AGGREGATOR`.

Модель:

- `glm-5.3-flash`.

Для сравнения сохранялись:

- одинаковые traces;
- одинаковые 5 HaluMem-кейсов;
- одинаковые 5 retrieval policies;
- одинаковые инструкции judges;
- одинаковый формат итогового verdict.

---

## Independent baseline

В baseline-варианте четыре специализированных judges независимо анализируют retrieved context:

`CONSISTENCY_JUDGE`

`TEMPORAL_JUDGE`

`EVIDENCE_JUDGE`

`OUT_OF_SLICE_JUDGE`

После этого `FINAL_AGGREGATOR` получает результаты всех четырёх проверок и формирует итоговую оценку.

---

## Sequential experiment

В sequential-варианте был построен DAG с накоплением промежуточного контекста:

`CONSISTENCY_JUDGE`
→ `TEMPORAL_JUDGE`
→ `EVIDENCE_JUDGE`
→ `OUT_OF_SLICE_JUDGE`
→ `FINAL_AGGREGATOR`.

Более поздние judges получают исходный retrieved context и результаты предыдущих специализированных проверок.

Всего выполнено:

- 5 HaluMem cases;
- 5 retrieval policies;
- 25 sequential evaluations.

---

## Результаты

По признаку `supports_answer` результаты independent и sequential вариантов совпали:

| Retrieval policy | Independent judges | Sequential judges |
|---|---:|---:|
| `flat_bm25` | 5/5 | 5/5 |
| `query_aware` | 3/5 | 3/5 |
| `before_aware` | 2/5 | 2/5 |
| `strict_temporal` | 2/5 | 2/5 |
| `transition_aware` | 2/5 | 2/5 |

Передача промежуточных результатов между judges не изменила evidence sufficiency на выбранной репрезентативной выборке.

---

## Изменения semantic verdicts

Несмотря на одинаковый результат по `supports_answer`, отдельные semantic verdicts изменились.

Например, для:

`halumem-memory-conflict-027`

с retrieval policy:

`query_aware`

independent-вариант дал:

- `consistency_status = conflicting`;
- `conflict_type = true_conflict`;
- `missing_required_evidence = true`;
- `supports_answer = false`.

Sequential-вариант дал:

- `consistency_status = consistent`;
- `conflict_type = none`;
- `missing_required_evidence = true`;
- `supports_answer = false`.

Таким образом, передача промежуточных выводов изменила интерпретацию retrieved context, но не решила основную retrieval-проблему: необходимый evidence всё равно отсутствовал.

---

## Сохранившаяся проблема taxonomy

Sequential-вариант не устранил все несогласованности semantic evaluation.

В части результатов по-прежнему встречается сочетание:

- `consistency_status = conflicting`;
- `conflict_type = temporal_update`.

При этом `temporal_update` в принятой постановке должен обозначать нормальное изменение состояния во времени, а не настоящий same-time conflict.

Следовательно, одной последовательной организации judges недостаточно для устранения неоднозначности между legitimate temporal update и true conflict.

---

## Вывод

На текущей выборке sequential judges не показали преимущества над independent judges по `supports_answer`.

Основной результат:

- evidence sufficiency не изменилась;
- отдельные semantic classifications изменились;
- проблема различения temporal update и true conflict полностью не исчезла.

Поэтому эксперимент рассматривается как дополнительный архитектурный анализ AutoJudge, а не как доказательство преимущества sequential pipeline.

Основная проблема остаётся на уровне retrieval: система должна сохранять evidence, необходимый для ответа, одновременно избегая вредных конфликтующих или устаревших фактов.
