"""Генерация синтетической выгрузки Яндекс.Метрики для интернет-магазина электроники."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TypedDict

import numpy as np
import pandas as pd

# Корень проекта: scripts/ -> родительская папка
ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "data" / "raw" / "yandex_metrics_raw.csv"

# Базовый уровень буднего дня вне праздников
BASE_SESSIONS = 5600
RANDOM_SEED = 42
START = date(2025, 11, 1)
END = date(2026, 4, 30)


class Profile(TypedDict):
    """Связка устройства, браузера и ОС с долей трафика."""

    device_type: str
    browser: str
    os: str
    weight: float


# Доли подобраны так, чтобы смартфоны были около 60%, десктоп около 35%, планшеты около 5%
PROFILES: list[Profile] = [
    {"device_type": "mobile", "browser": "Chrome", "os": "Android", "weight": 0.26},
    {"device_type": "mobile", "browser": "Яндекс.Браузер", "os": "Android", "weight": 0.13},
    {"device_type": "mobile", "browser": "Safari", "os": "iOS", "weight": 0.15},
    {"device_type": "mobile", "browser": "Chrome", "os": "iOS", "weight": 0.04},
    {"device_type": "mobile", "browser": "Яндекс.Браузер", "os": "iOS", "weight": 0.02},
    {"device_type": "desktop", "browser": "Chrome", "os": "Windows", "weight": 0.13},
    {"device_type": "desktop", "browser": "Яндекс.Браузер", "os": "Windows", "weight": 0.09},
    {"device_type": "desktop", "browser": "Edge", "os": "Windows", "weight": 0.055},
    {"device_type": "desktop", "browser": "Firefox", "os": "Windows", "weight": 0.02},
    {"device_type": "desktop", "browser": "Safari", "os": "macOS", "weight": 0.03},
    {"device_type": "desktop", "browser": "Chrome", "os": "macOS", "weight": 0.015},
    {"device_type": "desktop", "browser": "Firefox", "os": "Linux", "weight": 0.01},
    {"device_type": "tablet", "browser": "Safari", "os": "iOS", "weight": 0.03},
    {"device_type": "tablet", "browser": "Chrome", "os": "Android", "weight": 0.015},
    {"device_type": "tablet", "browser": "Яндекс.Браузер", "os": "Android", "weight": 0.005},
]

# Organic и paid — основные источники
SOURCES: list[tuple[str, float]] = [
    ("organic", 0.40),
    ("paid", 0.27),
    ("direct", 0.18),
    ("social", 0.09),
    ("referral", 0.06),
]

COUNTRIES: list[tuple[str, float]] = [
    ("Россия", 0.76),
    ("Беларусь", 0.07),
    ("Казахстан", 0.08),
    ("Украина", 0.04),
    ("другие", 0.05),
]

# Базовая конверсия по устройству. После смеси источников получается около 3%
DEVICE_CR: dict[str, float] = {"desktop": 0.034, "mobile": 0.023, "tablet": 0.027}
SOURCE_CR: dict[str, float] = {
    "organic": 1.05,
    "direct": 1.28,
    "paid": 1.08,
    "social": 0.60,
    "referral": 0.86,
}
COUNTRY_CR: dict[str, float] = {
    "Россия": 1.00,
    "Беларусь": 0.96,
    "Казахстан": 0.97,
    "Украина": 0.94,
    "другие": 0.88,
}

DEVICE_PAGES: dict[str, float] = {"desktop": 3.9, "mobile": 2.55, "tablet": 3.05}
SOURCE_PAGES: dict[str, float] = {
    "organic": 1.12,
    "direct": 1.15,
    "paid": 0.90,
    "social": 0.82,
    "referral": 1.00,
}

DEVICE_BOUNCE: dict[str, float] = {"desktop": 0.32, "mobile": 0.47, "tablet": 0.40}
SOURCE_BOUNCE: dict[str, float] = {
    "organic": 0.90,
    "direct": 0.84,
    "paid": 1.12,
    "social": 1.22,
    "referral": 1.00,
}

DEVICE_DURATION: dict[str, float] = {"desktop": 250, "mobile": 130, "tablet": 175}
DEVICE_AOV: dict[str, float] = {"desktop": 14800, "mobile": 8700, "tablet": 11000}
SOURCE_AOV: dict[str, float] = {
    "organic": 1.00,
    "direct": 1.08,
    "paid": 0.92,
    "social": 0.84,
    "referral": 0.97,
}

# Доля пользователей от сессий: у прямых заходов больше повторных визитов в тот же день
USER_RATIO: dict[str, float] = {
    "direct": 0.74,
    "organic": 0.83,
    "paid": 0.92,
    "social": 0.90,
    "referral": 0.86,
}

RAW_COLUMNS = [
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


def season_multiplier(day: date) -> float:
    """Сезонный и недельный коэффициент числа сессий."""
    month_level = {11: 1.00, 12: 1.38, 1: 0.76, 2: 0.94, 3: 1.04, 4: 1.08}[day.month]
    event = 1.0

    # Распродажа 11.11 и чёрная пятница
    if (day.month, day.day) == (11, 11):
        event = 1.75
    elif day.month == 11 and day.day in (10, 12):
        event = 1.22
    elif day.month == 11 and 24 <= day.day <= 30:
        event = 2.10 if day.day == 28 else 1.50
    # Предновогодний спрос держится всю вторую половину декабря
    elif day.month == 12 and 12 <= day.day <= 28:
        event = 1.20 + 0.035 * min(day.day - 12, 12)
    elif (day.month, day.day) == (12, 31):
        event = 0.72
    elif day.month == 1 and day.day <= 8:
        event = 0.55
    elif (day.month, day.day) == (2, 14):
        event = 1.18
    elif day.month == 2 and day.day in (21, 22, 23):
        event = 1.16
    elif day.month == 3 and day.day in (6, 7, 8):
        event = 1.42

    weekday_factor = [0.98, 1.02, 1.04, 1.06, 1.08, 0.87, 0.79][day.weekday()]
    return month_level * event * weekday_factor


def commercial_factors(day: date) -> tuple[float, float]:
    """Коэффициенты конверсии и среднего чека для праздников и выходных."""
    conversion = 1.0
    aov = 1.0
    if day.month == 12:
        conversion *= 1.10
        aov *= 1.24
    if day.month == 1 and day.day <= 8:
        conversion *= 0.70
        aov *= 0.90
    if day.month == 11 and 24 <= day.day <= 30:
        conversion *= 1.12
        aov *= 0.88
    if day.month == 3 and day.day in (6, 7, 8):
        conversion *= 1.16
        aov *= 1.10
    if day.weekday() >= 5:
        conversion *= 0.94
    return conversion, aov


def source_weights(day: date) -> np.ndarray:
    """Доли источников с усилением платного трафика в сезон рекламы."""
    weights = {name: value for name, value in SOURCES}
    if day.month == 12 or (day.month == 11 and day.day >= 24):
        weights["paid"] *= 1.40
        weights["social"] *= 1.12
        weights["organic"] *= 0.88
    elif day.month == 1:
        weights["paid"] *= 0.72
        weights["direct"] *= 1.12
    ordered = np.array([weights[name] for name, _ in SOURCES], dtype=float)
    return ordered / ordered.sum()


def profile_weights(day: date) -> np.ndarray:
    """Доли устройств: в декабре чуть больше десктопа, в выходные — смартфонов."""
    weights = np.array([item["weight"] for item in PROFILES], dtype=float)
    for index, item in enumerate(PROFILES):
        device = item["device_type"]
        if day.month == 12:
            if device == "desktop":
                weights[index] *= 1.18
            elif device == "mobile":
                weights[index] *= 0.90
        if day.weekday() >= 5:
            if device == "mobile":
                weights[index] *= 1.10
            elif device == "desktop":
                weights[index] *= 0.86
    return weights / weights.sum()


def segment_weights(day: date, rng: np.random.Generator) -> tuple[list[tuple[str, Profile, str]], np.ndarray]:
    """Веса всех сочетаний источник × устройство × страна на один день."""
    sources = source_weights(day)
    profiles = profile_weights(day)
    keys: list[tuple[str, Profile, str]] = []
    weights: list[float] = []
    for source_index, (source, _) in enumerate(SOURCES):
        for profile_index, profile in enumerate(PROFILES):
            for country, country_weight in COUNTRIES:
                keys.append((source, profile, country))
                weights.append(sources[source_index] * profiles[profile_index] * country_weight)
    array = np.asarray(weights, dtype=float)
    # Небольшой ежедневный шум, чтобы доли не были идеально ровными
    array *= rng.lognormal(mean=0.0, sigma=0.045, size=array.shape)
    array /= array.sum()
    return keys, array


def build_row(
    day: date,
    sessions: int,
    source: str,
    profile: Profile,
    country: str,
    rng: np.random.Generator,
) -> dict[str, object]:
    """Собирает метрики одного сегмента так, чтобы они были согласованы между собой."""
    device = profile["device_type"]
    conversion_factor, aov_factor = commercial_factors(day)
    conversion_rate = (
        DEVICE_CR[device]
        * SOURCE_CR[source]
        * COUNTRY_CR[country]
        * conversion_factor
        * float(rng.normal(1.0, 0.06))
    )
    conversion_rate = float(np.clip(conversion_rate, 0.008, 0.07))
    conversions = int(rng.binomial(sessions, conversion_rate))

    pages = DEVICE_PAGES[device] * SOURCE_PAGES[source] * float(rng.normal(1.0, 0.05))
    pages = float(np.clip(pages, 1.4, 7.0))
    pageviews = max(sessions, int(round(sessions * pages)))
    pages_per_session = pageviews / sessions

    bounce = DEVICE_BOUNCE[device] * SOURCE_BOUNCE[source] * float(rng.normal(1.0, 0.04))
    # Глубокий просмотр снижает долю отказов
    bounce *= (3.1 / pages_per_session) ** 0.30
    bounce = float(np.clip(bounce, 0.12, 0.78))

    duration = DEVICE_DURATION[device] * (pages_per_session / DEVICE_PAGES[device]) ** 0.45
    duration *= 1.05 + (0.45 - bounce)
    duration *= float(rng.normal(1.0, 0.04))
    duration = float(np.clip(duration, 45, 640))

    user_ratio = float(np.clip(USER_RATIO[source] * rng.normal(1.0, 0.02), 0.65, 0.98))
    users = int(np.clip(round(sessions * user_ratio), 1, sessions))

    aov = DEVICE_AOV[device] * SOURCE_AOV[source] * aov_factor * float(rng.normal(1.0, 0.08))
    aov = float(np.clip(aov, 2500, 45000))
    revenue = round(conversions * aov, 2) if conversions else 0.0

    return {
        "date": day.isoformat(),
        "sessions": sessions,
        "users": users,
        "pageviews": pageviews,
        "bounce_rate": round(bounce * 100, 2),
        "avg_session_duration": round(duration, 1),
        "pages_per_session": round(pages_per_session, 2),
        "traffic_source": source,
        "device_type": device,
        "browser": profile["browser"],
        "os": profile["os"],
        "country": country,
        "conversions": conversions,
        "revenue": revenue,
    }


def generate(rng: np.random.Generator) -> pd.DataFrame:
    """Строит дневные сегменты за весь период."""
    rows: list[dict[str, object]] = []
    for stamp in pd.date_range(START, END, freq="D"):
        day = stamp.date()
        noise = float(np.clip(rng.normal(1.0, 0.03), 0.90, 1.10))
        total_sessions = max(1, int(round(BASE_SESSIONS * season_multiplier(day) * noise)))
        keys, weights = segment_weights(day, rng)
        counts = rng.multinomial(total_sessions, weights)
        for (source, profile, country), sessions in zip(keys, counts):
            if int(sessions) == 0:
                continue
            rows.append(build_row(day, int(sessions), source, profile, country, rng))

    frame = pd.DataFrame(rows, columns=RAW_COLUMNS)
    frame = frame.sort_values(
        ["date", "traffic_source", "device_type", "browser", "os", "country"]
    ).reset_index(drop=True)
    return frame


def inject_gaps(frame: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Добавляет редкие пропуски, чтобы шаг очистки в обработке был на реальных ячейках."""
    result = frame.copy()
    for column, count in (("bounce_rate", 6), ("avg_session_duration", 6)):
        positions = rng.choice(len(result), size=count, replace=False)
        result.iloc[positions, result.columns.get_loc(column)] = np.nan
    return result


def save_raw(frame: pd.DataFrame, path: Path) -> None:
    """Записывает CSV в кодировке, которую Excel и Power BI открывают с кириллицей."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False, encoding="utf-8-sig")
    except OSError as exc:
        raise OSError(f"Не удалось записать файл: {path}") from exc


def print_summary(frame: pd.DataFrame) -> None:
    """Печатает контрольные доли, чтобы глазами проверить реализм выгрузки."""
    sessions = float(frame["sessions"].sum())
    print(f"Строк: {len(frame)}")
    print(f"Сессий: {int(sessions)}")
    print(f"Конверсия: {frame['conversions'].sum() / sessions * 100:.2f}%")
    print("Устройства:")
    print((frame.groupby("device_type")["sessions"].sum() / sessions * 100).round(1).to_string())
    print("Источники:")
    print((frame.groupby("traffic_source")["sessions"].sum() / sessions * 100).round(1).to_string())
    by_month = frame.copy()
    by_month["date"] = pd.to_datetime(by_month["date"])
    monthly = by_month.groupby(by_month["date"].dt.to_period("M"))["sessions"].sum()
    print("Сессии по месяцам:")
    print(monthly.to_string())


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    frame = generate(rng)
    print_summary(frame)
    frame = inject_gaps(frame, rng)
    save_raw(frame, RAW_PATH)
    print(f"Сохранено: {RAW_PATH}")


if __name__ == "__main__":
    main()
