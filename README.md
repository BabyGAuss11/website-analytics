# Анализ посещаемости интернет-магазина

Учебный проект со синтетическими данными в формате выгрузки Яндекс.Метрики. Сайта нет: цифры сгенерированы для вымышленного интернет-магазина электроники за ноябрь 2025 — апрель 2026.

## Цель проекта

Собрать полный цикл аналитики посещаемости без доступа к реальному счётчику:

1. получить «сырую» выгрузку;
2. проверить её, посчитать производные метрики и нарезать срезы;
3. построить графики в Jupyter Notebook;
4. отдать плоскую таблицу в Power BI.


## Описание данных



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

