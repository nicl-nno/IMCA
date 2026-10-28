# AutoJudge: GLM vs Jev evaluation

## Цель

Дополнительно была проверена устойчивость semantic evaluation к выбору evaluator-модели.

Основной вопрос:

> Насколько выводы о качестве retrieved context зависят от конкретного evaluator?

Для сравнения использовались:

- `glm-5.3-flash`;
- `typesafe/jev-1.14`.

Оба evaluator проверялись на одинаковых:

- 5 репрезентативных HaluMem `Memory Conflict` кейсах;
- 5 retrieval policies;
- 25 retrieved contexts.

---

## Retrieval policies

Сравнивались:

- `flat_bm25`;
- `query_aware`;
- `before_aware`;
- `strict_temporal`;
- `transition_aware`.

Основным полем для сравнения было:

`supports_answer`

То есть достаточно ли retrieved context для того, чтобы определить правильный ответ на вопрос.

Также сравнивались:

- `consistency_status`;
- `conflict_type`;
- `out_of_slice_evidence`;
- `missing_required_evidence`.

---

## Первый Jev-прогон

В первом варианте Jev получал:

- Unix timestamps;
- `active_at_question_time`;
- `diagnostic_signals`;
- reference evidence.

Получились заметные расхождения с GLM.

По `supports_answer`:

| Retrieval policy | GLM | Jev v1 |
|---|---:|---:|
| `flat_bm25` | 5/5 | 3/5 |
| `query_aware` | 3/5 | 1/5 |
| `before_aware` | 2/5 | 0/5 |
| `strict_temporal` | 2/5 | 0/5 |
| `transition_aware` | 2/5 | 1/5 |

Также Jev часто классифицировал `out_of_slice_evidence` как `harmful` даже в случаях, где все retrieved memories имели `active_at_question_time=true`.

Это показало, что часть расхождений может быть связана не только с evaluator-моделью, но и с форматом входного состояния.

---

## Jev v2

Для второго прогона вход был сделан более явным и детерминированным.

Изменения:

- Unix timestamps были заранее преобразованы в календарные даты;
- отдельно передавалась `question_date`;
- `diagnostic_signals` были удалены из evaluator input;
- `active_at_question_time` оставлен как авторитетный временной признак;
- отдельно уточнено правило:
  если все retrieved memories имеют `active_at_question_time=true`, то `out_of_slice_evidence = none`;
- уточнено различие между `true_conflict` и `temporal_update`;
- уточнено сравнение retrieved memories с reference evidence.

После этого результаты Jev значительно приблизились к GLM.

---

## Результаты по supports_answer

| Retrieval policy | GLM | Jev v2 |
|---|---:|---:|
| `flat_bm25` | 5/5 | 5/5 |
| `query_aware` | 3/5 | 3/5 |
| `before_aware` | 2/5 | 1/5 |
| `strict_temporal` | 2/5 | 1/5 |
| `transition_aware` | 2/5 | 2/5 |

По `supports_answer` GLM и Jev v2 совпали:

- 23 из 25 случаев;
- 92%.

Расхождения остались только для:

- `halumem-memory-conflict-009__before_aware`;
- `halumem-memory-conflict-009__strict_temporal`.

---

## Согласие по отдельным полям

После перехода к Jev v2:

| Поле | Совпало |
|---|---:|
| `consistency_status` | 20/25 |
| `conflict_type` | 20/25 |
| `out_of_slice_evidence` | 24/25 |
| `missing_required_evidence` | 21/25 |
| `supports_answer` | 23/25 |

Наиболее устойчивым оказался `out_of_slice_evidence`.

Более заметные расхождения сохраняются для:

- общей consistency classification;
- различения `true_conflict` и `temporal_update`;
- определения наличия required evidence.

---

## Разбор оставшихся расхождений

Оба оставшихся расхождения по `supports_answer` относятся к одному кейсу:

`halumem-memory-conflict-009`

Вопрос:

> Did Donna's strategic shift to mobile device refurbishment begin in 2024?

В `before_aware` и `strict_temporal` retrieved context не содержит точного benchmark reference evidence:

> Donna decided to shift ReviveTech Solutions' focus to include mobile device refurbishment due to increasing demand in this sector.

Однако retrieved memories содержат косвенные временные признаки:

- в конце 2025 года есть стратегический план входа в рынок;
- в 2026 году уже наблюдаются последствия этого перехода.

GLM использует эти temporal anchors и делает косвенный вывод:

- переход не мог начаться в 2024 году;
- следовательно, context достаточен для отрицательного ответа.

Jev v2 оценивает ситуацию строже:

- benchmark reference evidence отсутствует;
- поэтому `missing_required_evidence = true`;
- `supports_answer = false`.

Таким образом, расхождение связано не только с evaluator-моделью, но и с различием между двумя понятиями:

1. наличие benchmark reference evidence;
2. возможность вывести правильный ответ из косвенного контекста.

---

## Вывод

После нормализации evaluator input Jev в основном подтвердил результаты GLM.

По `supports_answer` совпадение составило 23/25.

Основной ranking retrieval policies также сохранился:

- `flat_bm25` лучше всего сохраняет evidence, достаточный для ответа;
- `query_aware` занимает промежуточную позицию;
- более строгие temporal policies чаще теряют часть необходимого контекста.

При этом semantic classification остаётся менее стабильной:

- evaluator-модели могут по-разному различать `true_conflict` и `temporal_update`;
- наличие exact reference evidence и возможность косвенного inference не являются одним и тем же критерием.

Это показывает, что в дальнейшем полезно отдельно различать:

- `reference_evidence_present`;
- `answer_inferable`.

Такое разделение позволит точнее оценивать retrieval quality и не смешивать наличие benchmark evidence с возможностью логически вывести правильный ответ.
