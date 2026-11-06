"""Очистка синтетической выгрузки и подготовка срезов для анализа и Power BI."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "data" / "raw" / "yandex_metrics_raw.csv"
PROCESSED = ROOT / "data" / "processed"

RANDOM_SEED = 42

REQUIRED_COLUMNS = [
    "date",
    "sessions",
    "users",
    "pageviews",
    "bounce_rate",
    "avg_session_duration",
    "pages_per_session",
    "traffic_source",
    "device_type",
    "browser",
    "os",
    "country",
    "conversions",
    "revenue",
]

NUMERIC_COLUMNS = [
    "sessions",
    "users",
    "pageviews",
    "bounce_rate",
    "avg_session_duration",
    "pages_per_session",
    "conversions",
    "revenue",
]

# Доля новых посетителей внутри сегмента. Прямые заходы чаще возвращаются.
NEW_USER_SHARE = {
    "paid": 0.74,
    "social": 0.68,
    "referral": 0.52,
    "organic": 0.46,
    "direct": 0.32,
    "не указано": 0.50,
}

SOURCE_RU = {
    "organic": "Органический поиск",
    "paid": "Платная реклама",
    "direct": "Прямые заходы",
    "social": "Социальные сети",
    "referral": "Переходы с сайтов",
}
DEVICE_RU = {"mobile": "Смартфон", "desktop": "Десктоп", "tablet": "Планшет"}
MONTHS_RU = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}
WEEKDAY_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

# Типичный суточный профиль магазина. В сырой выгрузке часа нет, поэтому
# дневные сессии раскладываются по этим долям на шаге обработки.
RAW_WEEKDAY_HOURS = np.array(
    [
        1.1, 0.6, 0.35, 0.25, 0.25, 0.55,
        1.5, 2.8, 4.2, 5.1, 5.5, 5.7,
        6.0, 5.6, 5.2, 5.1, 5.4, 5.9,
        6.4, 7.0, 7.2, 6.5, 4.6, 2.6,
    ],
    dtype=float,
)
RAW_WEEKEND_HOURS = np.array(
    [
        1.8, 1.0, 0.55, 0.35, 0.30, 0.40,
        0.75, 1.5, 2.5, 3.7, 4.8, 5.6,
        6.2, 6.4, 6.1, 5.8, 5.6, 5.9,
        6.6, 7.4, 7.8, 7.5, 6.0, 3.4,
    ],
    dtype=float,
)

POWERBI_COLUMNS = [
    "date",
    "year",
    "month",
    "month_name",
    "year_month",
    "week_start",
    "iso_week",
    "weekday",
    "weekday_num",
    "traffic_source",
    "traffic_source_ru",
    "device_type",
    "device_type_ru",
    "browser",
    "os",
    "country",
    "sessions",
    "users",
    "new_users",
    "returning_users",
    "pageviews",
    "bounced_sessions",
    "total_duration_sec",
    "bounce_rate",
    "avg_session_duration",
    "pages_per_session",
    "conversions",
    "revenue",
    "conversion_rate",
    "revenue_per_session",
    "new_vs_returning",
]


def read_raw(path: Path) -> pd.DataFrame:
    """Читает сырой CSV и переводит сбои в понятные сообщения."""
    if not path.exists():
        raise FileNotFoundError(
            f"Файл не найден: {path}. Сначала запустите scripts/generate_data.py."
        )
    if path.stat().st_size == 0:
        raise ValueError(f"Файл пустой: {path}")
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"В файле нет таблицы: {path}") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(f"CSV не разбирается: {path}") from exc
    except OSError as exc:
        raise OSError(f"Ошибка чтения файла: {path}") from exc
    if frame.empty:
        raise ValueError(f"В файле нет строк: {path}")
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError("В выгрузке нет колонок: " + ", ".join(missing))
    return frame


def fill_numeric(series: pd.Series, fallback: float) -> pd.Series:
    """Заполняет пропуски медианой столбца."""
    median = series.median()
    if pd.isna(median):
        median = fallback
    return series.fillna(float(median))


def clean(frame: pd.DataFrame) -> pd.DataFrame:
    """Проверяет типы, закрывает пропуски и чинит невозможные сочетания метрик."""
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    broken_dates = int(data["date"].isna().sum())
    if broken_dates:
        print(f"Строк с нечитаемой датой: {broken_dates}. Они удалены.")
        data = data.dropna(subset=["date"])

    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    gaps = data.isna().sum()
    gaps = gaps[gaps > 0]
    if gaps.empty:
        print("Пропусков нет.")
    else:
        print("Пропуски до заполнения:")
        print(gaps.to_string())

    for column in ("traffic_source", "device_type", "browser", "os", "country"):
        data[column] = data[column].fillna("не указано").astype(str).str.strip()

    before = len(data)
    data = data.drop_duplicates()
    print(f"Удалено полных дубликатов: {before - len(data)}")

    # Сессии — ключ для всех долей. Строку без сессий нельзя осмысленно оставить.
    data["sessions"] = fill_numeric(data["sessions"], 0)
    dropped = int((data["sessions"] <= 0).sum() + data["sessions"].isna().sum())
    data = data[data["sessions"] > 0].copy()
    if dropped:
        print(f"Удалено строк без сессий: {dropped}")

    data["users"] = fill_numeric(data["users"], 1)
    data["pageviews"] = fill_numeric(data["pageviews"], 1)
    data["bounce_rate"] = fill_numeric(data["bounce_rate"], 40)
    data["avg_session_duration"] = fill_numeric(data["avg_session_duration"], 150)
    data["conversions"] = fill_numeric(data["conversions"], 0)
    data["revenue"] = fill_numeric(data["revenue"], 0)

    data["sessions"] = data["sessions"].round().astype(int)
    data["users"] = data["users"].round().clip(lower=1, upper=data["sessions"]).astype(int)
    data["conversions"] = data["conversions"].round().clip(lower=0, upper=data["sessions"]).astype(int)
    data["pageviews"] = data["pageviews"].round().clip(lower=data["sessions"]).astype(int)
    data["bounce_rate"] = data["bounce_rate"].clip(lower=0, upper=100)
    data["avg_session_duration"] = data["avg_session_duration"].clip(lower=1)
    data["revenue"] = data["revenue"].clip(lower=0)
    data.loc[data["conversions"] == 0, "revenue"] = 0.0

    data["bounced_sessions"] = (
        (data["sessions"] * data["bounce_rate"] / 100).round().clip(upper=data["sessions"]).astype(int)
    )
    data["total_duration_sec"] = data["avg_session_duration"] * data["sessions"]
    add_ratios(data)
    add_new_and_returning(data)
    add_calendar(data)
    return data.sort_values(
        ["date", "traffic_source", "device_type", "browser", "os", "country"]
    ).reset_index(drop=True)


def add_ratios(data: pd.DataFrame) -> None:
    """Считает производные метрики из аддитивных колонок."""
    sessions = data["sessions"].replace(0, np.nan)
    data["pages_per_session"] = data["pageviews"] / sessions
    data["bounce_rate"] = data["bounced_sessions"] / sessions * 100
    data["avg_session_duration"] = data["total_duration_sec"] / sessions
    data["conversion_rate"] = data["conversions"] / sessions * 100
    data["revenue_per_session"] = data["revenue"] / sessions


def add_new_and_returning(data: pd.DataFrame) -> None:
    """Имитирует новых и вернувшихся посетителей по источнику трафика."""
    base_share = data["traffic_source"].map(NEW_USER_SHARE).fillna(0.50)
    # Детерминированный сдвиг ±5 п.п., чтобы повторный запуск давал тот же файл
    day_of_year = data["date"].dt.dayofyear
    noise = ((data["sessions"] * 17 + day_of_year) % 11 - 5) / 100
    share = (base_share + noise).clip(lower=0.15, upper=0.90)
    data["new_users"] = (data["users"] * share).round().clip(upper=data["users"]).astype(int)
    data["returning_users"] = (data["users"] - data["new_users"]).astype(int)
    users = data["users"].replace(0, np.nan)
    data["new_vs_returning"] = (data["new_users"] / users * 100).fillna(0)


def add_calendar(data: pd.DataFrame) -> None:
    """Добавляет календарные поля для срезов и Power BI."""
    data["year"] = data["date"].dt.year.astype(int)
    data["month"] = data["date"].dt.month.astype(int)
    data["month_name"] = data["month"].map(MONTHS_RU)
    data["year_month"] = data["date"].dt.strftime("%Y-%m")
    data["month_label"] = data["month_name"] + " " + data["year"].astype(str)
    data["weekday_num"] = data["date"].dt.weekday.astype(int)
    data["weekday"] = data["weekday_num"].map(lambda number: WEEKDAY_RU[int(number)])
    data["week_start"] = (data["date"] - pd.to_timedelta(data["weekday_num"], unit="D")).dt.date
    iso = data["date"].dt.isocalendar()
    data["iso_week"] = iso.week.astype(int)
    data["traffic_source_ru"] = data["traffic_source"].map(SOURCE_RU).fillna(data["traffic_source"])
    data["device_type_ru"] = data["device_type"].map(DEVICE_RU).fillna(data["device_type"])


def aggregate(data: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Сворачивает сегменты. Коэффициенты считаются заново из сумм, а не усредняются."""
    grouped = data.groupby(keys, as_index=False, dropna=False).agg(
        sessions=("sessions", "sum"),
        users=("users", "sum"),
        new_users=("new_users", "sum"),
        returning_users=("returning_users", "sum"),
        pageviews=("pageviews", "sum"),
        bounced_sessions=("bounced_sessions", "sum"),
        total_duration_sec=("total_duration_sec", "sum"),
        conversions=("conversions", "sum"),
        revenue=("revenue", "sum"),
    )
    sessions = grouped["sessions"].replace(0, np.nan)
    users = grouped["users"].replace(0, np.nan)
    grouped["bounce_rate"] = (grouped["bounced_sessions"] / sessions * 100).fillna(0)
    grouped["avg_session_duration"] = (grouped["total_duration_sec"] / sessions).fillna(0)
    grouped["pages_per_session"] = (grouped["pageviews"] / sessions).fillna(0)
    grouped["conversion_rate"] = (grouped["conversions"] / sessions * 100).fillna(0)
    grouped["revenue_per_session"] = (grouped["revenue"] / sessions).fillna(0)
    grouped["new_vs_returning"] = (grouped["new_users"] / users * 100).fillna(0)
    return grouped


def round_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Округляет выгрузку, сохраняя целые счётчики целыми."""
    result = frame.copy()
    integer_columns = [
        "sessions",
        "users",
        "new_users",
        "returning_users",
        "pageviews",
        "bounced_sessions",
        "conversions",
        "year",
        "month",
        "iso_week",
        "weekday_num",
        "hour",
    ]
    for column in integer_columns:
        if column in result.columns:
            result[column] = result[column].round().astype(int)
    for column in ("bounce_rate", "pages_per_session", "conversion_rate", "new_vs_returning", "revenue_per_session", "revenue"):
        if column in result.columns:
            result[column] = result[column].round(2)
    if "avg_session_duration" in result.columns:
        result["avg_session_duration"] = result["avg_session_duration"].round(1)
    if "total_duration_sec" in result.columns:
        result["total_duration_sec"] = result["total_duration_sec"].round(1)
    return result


def build_hourly(daily: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Раскладывает дневные сессии по часам отдельным профилем для будней и выходных."""
    weekday_profile = RAW_WEEKDAY_HOURS / RAW_WEEKDAY_HOURS.sum()
    weekend_profile = RAW_WEEKEND_HOURS / RAW_WEEKEND_HOURS.sum()
    records: list[dict[str, object]] = []
    for row in daily.itertuples(index=False):
        profile = weekend_profile.copy() if int(row.weekday_num) >= 5 else weekday_profile.copy()
        if int(row.weekday_num) == 4:
            profile[18:23] *= 1.12
        profile = profile * rng.uniform(0.93, 1.07, size=24)
        profile = profile / profile.sum()
        counts = rng.multinomial(int(row.sessions), profile)
        for hour, sessions in enumerate(counts):
            records.append(
                {
                    "date": row.date.date().isoformat(),
                    "hour": hour,
                    "weekday": row.weekday,
                    "weekday_num": int(row.weekday_num),
                    "sessions": int(sessions),
                }
            )
    return pd.DataFrame(records)


def save_csv(frame: pd.DataFrame, path: Path) -> None:
    """Сохраняет срез в UTF-8 с BOM."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False, encoding="utf-8-sig")
    except OSError as exc:
        raise OSError(f"Не удалось записать файл: {path}") from exc


def save_monthly_excel(frame: pd.DataFrame, path: Path) -> None:
    """Дублирует месячный срез в Excel — зависимость openpyxl нужна именно здесь."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_excel(path, index=False, sheet_name="По месяцам", engine="openpyxl")
    except OSError as exc:
        raise OSError(f"Не удалось записать книгу Excel: {path}") from exc


def main() -> None:
    raw = read_raw(RAW_PATH)
    data = clean(raw)

    daily = aggregate(data, ["date", "year_month", "month_label", "weekday", "weekday_num"])
    daily = daily.sort_values("date")

    weekly = aggregate(data, ["week_start"])
    weekly = weekly.sort_values("week_start")

    monthly = aggregate(data, ["year", "month", "month_name", "year_month", "month_label"])
    monthly = monthly.sort_values(["year", "month"])

    by_source = aggregate(data, ["year_month", "month_label", "traffic_source", "traffic_source_ru"])
    by_source = by_source.sort_values(["year_month", "traffic_source"])

    by_device = aggregate(data, ["year_month", "month_label", "device_type", "device_type_ru"])
    by_device = by_device.sort_values(["year_month", "device_type"])

    by_source_device = aggregate(data, ["traffic_source", "traffic_source_ru", "device_type", "device_type_ru"])
    by_source_device = by_source_device.sort_values(["traffic_source", "device_type"])

    hourly = build_hourly(daily, np.random.default_rng(RANDOM_SEED))

    powerbi = round_frame(data[POWERBI_COLUMNS])
    outputs = {
        "daily_totals.csv": round_frame(daily),
        "weekly_metrics.csv": round_frame(weekly),
        "monthly_metrics.csv": round_frame(monthly),
        "by_traffic_source.csv": round_frame(by_source),
        "by_device.csv": round_frame(by_device),
        "by_source_device.csv": round_frame(by_source_device),
        "hourly_activity.csv": round_frame(hourly),
        "powerbi_ready.csv": powerbi,
    }
    for name, frame in outputs.items():
        destination = PROCESSED / name
        save_csv(frame, destination)
        print(f"Сохранено: {destination} ({len(frame)} строк)")

    excel_path = PROCESSED / "monthly_metrics.xlsx"
    save_monthly_excel(round_frame(monthly), excel_path)
    print(f"Сохранено: {excel_path}")

    total_sessions = int(data["sessions"].sum())
    conversion = data["conversions"].sum() / total_sessions * 100
    print(f"Итого сессий: {total_sessions}")
    print(f"Конверсия после очистки: {conversion:.2f}%")


if __name__ == "__main__":
    main()
