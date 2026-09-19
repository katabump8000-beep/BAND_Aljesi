from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class StrategyConfig:
    candle_count: int = 3
    entry_seconds_before_close: int = 22
    base_amount: float = 1.0
    multiplier: float = 2.0


def candle_color(candle):
    if candle["close"] > candle["open"]:
        return "GREEN"

    if candle["close"] < candle["open"]:
        return "RED"

    return "DOJI"


def get_signal(candles, config):
    if len(candles) < config.candle_count:
        return None

    selected = candles[-config.candle_count:]
    colors = [candle_color(candle) for candle in selected]

    if all(color == "GREEN" for color in colors):
        return "CALL"

    if all(color == "RED" for color in colors):
        return "PUT"

    return None


def get_entry_time(candle_close_time, config):
    return candle_close_time - timedelta(
        seconds=config.entry_seconds_before_close
    )


def is_entry_time(current_time, candle_close_time, config):
    target_time = get_entry_time(candle_close_time, config)

    return current_time >= target_time


def next_amount(current_amount, won, config):
    if won:
        return config.base_amount

    return current_amount * config.multiplier
