# Reference evidence vs answer inference

## Цель

В предыдущих экспериментах использовался общий признак:

`supports_answer`

Он отвечал на вопрос, достаточно ли retrieved context для ответа.

После сравнения GLM и Jev стало видно, что этот признак смешивает два разных свойства:

1. найден ли benchmark reference evidence;
2. можно ли всё равно вывести правильный ответ из retrieved context.

Поэтому эти понятия были разделены.

---

## Новые признаки

### reference_evidence_present

Проверяет, представлен ли в retrieved memories эталонный evidence из benchmark.

Точное совпадение формулировки не требуется: учитывается семантическое соответствие.

### answer_inferable

Проверяет, можно ли определить правильный ответ только из retrieved memories и их временной информации.

При этом answer может быть получен косвенно, даже если exact reference evidence не найден.

---

## Возможные варианты

Получаются четыре типа retrieved context:

1. `reference_evidence_present = true`
   и `answer_inferable = true`

   Эталонный evidence найден, и контекста достаточно для ответа.

2. `reference_evidence_present = false`
   и `answer_inferable = true`

   Эталонный evidence не найден, но ответ можно вывести косвенно.

   Этот случай обозначается как:

   `indirect_inference`

3. `reference_evidence_present = true`
   и `answer_inferable = false`

   Эталонный факт найден, но retrieved context всё равно недостаточен или неоднозначен.

4. `reference_evidence_present = false`
   и `answer_inferable = false`

   Retrieved context недостаточен.

---

## Эксперимент

Использовались те же:

- 5 репрезентативных HaluMem `Memory Conflict` кейсов;
- 5 retrieval policies;
- 25 retrieved contexts;
- evaluator `typesafe/jev-1.14`.

Оценивались отдельно:

- `reference_evidence_present`;
- `answer_inferable`.

---

## Результаты

| Retrieval policy | Reference evidence | Answer inferable | Indirect inference |
|---|---:|---:|---:|
| `flat_bm25` | 5/5 | 4/5 | 0 |
| `query_aware` | 3/5 | 2/5 | 0 |
| `transition_aware` | 2/5 | 2/5 | 0 |
| `before_aware` | 1/5 | 1/5 | 0 |
| `strict_temporal` | 0/5 | 1/5 | 1 |

---

## Indirect inference

Один потенциальный случай `indirect_inference` был найден для:

`halumem-memory-conflict-010__strict_temporal`

Результат:

- `reference_evidence_present = false`;
- `answer_inferable = true`;
- probability для наличия reference evidence = 0.46;
- probability для answer inferable = 0.61.

Таким образом, при пороге 0.5 evaluator считает, что benchmark reference evidence отсутствует, но оставшегося retrieved context достаточно для ответа.

При этом уверенность невысокая, поэтому этот результат следует рассматривать как потенциальный пример indirect inference, а не как окончательное доказательство.

---

## Evidence present, but answer not inferable

Также найдены обратные случаи.

Например:

`halumem-memory-conflict-001__flat_bm25`

имеет:

- `reference_evidence_present = true`;
- `answer_inferable = false`.

Аналогичный результат наблюдается для:

`halumem-memory-conflict-001__query_aware`.

Это показывает, что само наличие benchmark reference evidence не гарантирует, что весь retrieved context достаточен для однозначного ответа.

---

## Case 009

Для:

`halumem-memory-conflict-009`

GLM ранее считал, что в `before_aware` и `strict_temporal` правильный отрицательный ответ можно вывести из временных признаков.

Jev при разделении evidence и inference оценил оба случая как:

- `reference_evidence_present = false`;
- `answer_inferable = false`.

Таким образом, этот кейс остаётся примером evaluator disagreement.

GLM допускает более сильный косвенный temporal inference, тогда как Jev считает такой вывод недостаточно надёжным.

Этот случай не следует искусственно приводить к единому verdict.

---

## Вывод

`reference_evidence_present` и `answer_inferable` измеряют разные свойства retrieval context.

Наличие benchmark evidence не гарантирует answerability.

И наоборот, отсутствие benchmark evidence не всегда означает невозможность ответа: в отдельных случаях ответ может быть получен из косвенных временных и семантических признаков.

Поэтому дальнейшая evaluation retrieval quality должна по возможности отдельно учитывать:

- наличие reference evidence;
- возможность ответа;
- temporal consistency;
- наличие harmful stale/conflicting information.

Один общий признак `supports_answer` слишком грубо объединяет эти аспекты.
