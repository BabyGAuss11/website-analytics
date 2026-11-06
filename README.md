# Анализ посещаемости интернет-магазина

Учебный проект со синтетическими данными в формате выгрузки Яндекс.Метрики. Сайта нет: цифры сгенерированы для вымышленного интернет-магазина электроники за ноябрь 2025 — апрель 2026. По ним можно посмотреть сезонность, источники, устройства и подготовить отчёт в Power BI.

## Цель проекта

Собрать полный цикл аналитики посещаемости без доступа к реальному счётчику:

1. получить «сырую» выгрузку;
2. проверить её, посчитать производные метрики и нарезать срезы;
3. построить графики в Jupyter Notebook;
4. отдать плоскую таблицу в Power BI.

В данных заложены новогодний подъём в декабре, спад в январские каникулы, доля смартфонов около 60%, десктопа около 35%, планшетов около 5%. Основные источники — органический поиск и платная реклама. Общая конверсия держится в диапазоне 2–4%.

## Как запустить

Нужен Python 3.10 или новее. На Windows удобно вызывать интерпретатор как `py -3`.

Из корня проекта:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts\generate_data.py
python scripts\process_data.py
python -m jupyter notebook notebooks\analysis.ipynb
```

Если политика PowerShell не даёт активировать окружение:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Повторный запуск генератора с тем же зерном `42` воспроизводит тот же CSV. Обработка тоже детерминирована: доля новых и вернувшихся посетителей считается по формуле, а не случайным броском.

## Описание данных

Сырой файл `data/raw/yandex_metrics_raw.csv` — одна строка на день и сегмент (источник, устройство, браузер, ОС, страна).

| Колонка | Смысл |
| --- | --- |
| `date` | Дата |
| `sessions` | Сессии |
| `users` | Посетители внутри сегмента |
| `pageviews` | Просмотры страниц |
| `bounce_rate` | Отказы, % |
| `avg_session_duration` | Средняя длительность сессии, секунды |
| `pages_per_session` | Глубина просмотра |
| `traffic_source` | `organic`, `direct`, `social`, `referral`, `paid` |
| `device_type` | `desktop`, `mobile`, `tablet` |
| `browser` | Chrome, Safari, Firefox, Яндекс.Браузер, Edge |
| `os` | Windows, macOS, iOS, Android, Linux |
| `country` | Россия, Беларусь, Казахстан, Украина, другие |
| `conversions` | Целевые действия |
| `revenue` | Выручка, рубли |

В сыром файле намеренно оставлено несколько пустых ячеек в `bounce_rate` и `avg_session_duration`. Скрипт обработки заполняет их медианой столбца.

`users` — посетители сегмента за день. Сумма по сегментам близка к дневной аудитории, потому что пользователь в этой модели попадает в один сегмент. В настоящей Метрике один человек может встретиться в нескольких строках, и сумма «пользователей» по срезам больше числа уникальных посетителей сайта.

Почасовой разрез в сырой выгрузке отсутствует. `scripts/process_data.py` раскладывает дневные сессии по типичному профилю интернет-магазина: в будни подъём днём и вечером, в выходные позже. Результат лежит в `data/processed/hourly_activity.csv`. Это модель, а не выгрузка по часам из счётчика.

После обработки появляются:

- `conversion_rate` — конверсии / сессии × 100;
- `revenue_per_session` — выручка / сессии;
- `new_users`, `returning_users` и `new_vs_returning` — имитация новых и вернувшихся (доля новых, %).

Обработанные файлы в `data/processed/`:

| Файл | Содержимое |
| --- | --- |
| `daily_totals.csv` | Итог по дням |
| `weekly_metrics.csv` | Итог по неделям (неделя с понедельника) |
| `monthly_metrics.csv` | Итог по месяцам |
| `monthly_metrics.xlsx` | Тот же месячный итог в Excel |
| `by_traffic_source.csv` | Месяц × источник |
| `by_device.csv` | Месяц × устройство |
| `by_source_device.csv` | Источник × устройство за весь период |
| `hourly_activity.csv` | Дата × час |
| `powerbi_ready.csv` | Плоская таблица для Power BI |

Коэффициенты в агрегатах пересчитаны из сумм. Среднее из процентов отказов или конверсии не используется.

## Как подключить к Power BI

1. Откройте Power BI Desktop.
2. **Главная → Получить данные → Текст/CSV**.
3. Выберите `data/processed/powerbi_ready.csv`.
4. Кодировка — UTF-8. Разделитель — запятая.
5. Проверьте тип поля `date` (дата) и нажмите **Закрыть и применить**.

Для тепловой карты по часам загрузите вторым запросом `data/processed/hourly_activity.csv` и свяжите таблицы по полю `date` (многие ко многим не нужны: связь «часы» → «дата» в направлении от почасовой таблицы к календарю, если заведёте отдельную таблицу дат).

Колонки `bounce_rate`, `avg_session_duration`, `pages_per_session`, `conversion_rate`, `revenue_per_session` и `new_vs_returning` уже посчитаны на уровне строки. В визуализации их суммировать нечего: создайте меры от аддитивных полей.

```dax
Сессии = SUM ( metrics[sessions] )
Конверсия % = DIVIDE ( SUM ( metrics[conversions] ), [Сессии] ) * 100
Отказы % = DIVIDE ( SUM ( metrics[bounced_sessions] ), [Сессии] ) * 100
Время сессии, сек = DIVIDE ( SUM ( metrics[total_duration_sec] ), [Сессии] )
Страниц за сессию = DIVIDE ( SUM ( metrics[pageviews] ), [Сессии] )
Выручка на сессию = DIVIDE ( SUM ( metrics[revenue] ), [Сессии] )
Доля новых % = DIVIDE ( SUM ( metrics[new_users] ), SUM ( metrics[users] ) ) * 100
```

`metrics` замените на имя таблицы в модели. Для срезов удобны `traffic_source_ru`, `device_type_ru`, `country`, `browser`, `os`, `month_name`.

## Структура проекта

```
website-analytics/
├── data/
│   ├── raw/
│   │   └── yandex_metrics_raw.csv
│   └── processed/
│       ├── daily_totals.csv
│       ├── weekly_metrics.csv
│       ├── monthly_metrics.csv
│       ├── monthly_metrics.xlsx
│       ├── by_traffic_source.csv
│       ├── by_device.csv
│       ├── by_source_device.csv
│       ├── hourly_activity.csv
│       └── powerbi_ready.csv
├── notebooks/
│   └── analysis.ipynb
├── scripts/
│   ├── generate_data.py
│   └── process_data.py
├── requirements.txt
└── README.md
```

`scripts/generate_data.py` создаёт сырую выгрузку. `scripts/process_data.py` чистит её и пишет срезы. `notebooks/analysis.ipynb` строит графики: динамика по месяцам, доли источников, конверсия по устройствам, связь длительности сессии и конверсии, тепловая карта дня недели и часа.
