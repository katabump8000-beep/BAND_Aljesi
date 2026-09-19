from dataclasses import dataclass


@dataclass
class StrategyConfig:
    candle_count: int = 3
    entry_seconds_before_close: int = 22


def get_signal(candles, config: StrategyConfig):
    """
    candles: قائمة شموع، كل شمعة بالشكل:
    {"open": ..., "close": ...}

    يرجع:
    CALL = شراء
    PUT  = بيع
    None = لا توجد إشارة
    """

    if len(candles) < config.candle_count:
        return None

    last_candles = candles[-config.candle_count:]

    bullish = all(c["close"] > c["open"] for c in last_candles)
    bearish = all(c["close"] < c["open"] for c in last_candles)

    if bullish:
        return "CALL"

    if bearish:
        return "PUT"

    return None