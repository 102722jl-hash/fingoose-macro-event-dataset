"""Offline, auditable commodity continuous-series calculations for FinGoose v0.2.

The module deliberately accepts normalized mappings instead of making network
requests.  A later source adapter can convert Eastmoney (or another provider)
responses into the contract-daily shape consumed here.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence


class MarketDataError(ValueError):
    """Raised when market data cannot produce an auditable series."""


COMMODITY_SPECS: dict[str, dict[str, str]] = {
    "CU": {
        "name_cn": "沪铜",
        "exchange": "SHFE",
        "provider_market_id": "113",
        "quote_unit": "CNY_PER_TONNE",
        "contract_prefix": "cu",
        "vendor_main_code": "cum",
    },
    "SC": {
        "name_cn": "原油",
        "exchange": "INE",
        "provider_market_id": "142",
        "quote_unit": "CNY_PER_BARREL",
        "contract_prefix": "sc",
        "vendor_main_code": "scm",
    },
    "AU": {
        "name_cn": "沪金",
        "exchange": "SHFE",
        "provider_market_id": "113",
        "quote_unit": "CNY_PER_GRAM",
        "contract_prefix": "au",
        "vendor_main_code": "aum",
    },
    "I": {
        "name_cn": "铁矿石",
        "exchange": "DCE",
        "provider_market_id": "114",
        "quote_unit": "CNY_PER_TONNE",
        "contract_prefix": "i",
        "vendor_main_code": "im",
    },
}


def _coerce_date(value: str | date, field_name: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {value!r}") from exc


@dataclass(frozen=True)
class RollRule:
    """Parameters for the v1 open-interest main-contract rule."""

    confirmation_days: int = 2
    min_days_to_expiry: int = 5
    annualization_days: int = 252
    horizon_months: int = 3
    z_threshold: float = 0.5
    version: str = "fingoose-oi-main-v1"

    def __post_init__(self) -> None:
        if self.confirmation_days < 1:
            raise ValueError("confirmation_days must be positive")
        if self.min_days_to_expiry < 1:
            raise ValueError("min_days_to_expiry must be positive")
        if self.annualization_days < 1 or self.horizon_months < 1:
            raise ValueError("annualization_days and horizon_months must be positive")
        if self.z_threshold <= 0:
            raise ValueError("z_threshold must be positive")


@dataclass(frozen=True)
class TradingCalendar:
    """A bounded exchange calendar with explicit verification state."""

    exchange: str
    trading_dates: frozenset[date]
    coverage_start: date
    coverage_end: date
    verified: bool = False

    def __post_init__(self) -> None:
        if self.exchange not in {"SHFE", "INE", "DCE"}:
            raise ValueError(f"unsupported calendar exchange: {self.exchange!r}")
        if self.coverage_end < self.coverage_start:
            raise ValueError("calendar coverage_end precedes coverage_start")
        if any(
            item < self.coverage_start or item > self.coverage_end
            for item in self.trading_dates
        ):
            raise ValueError("trading date falls outside declared calendar coverage")

    @classmethod
    def from_values(
        cls,
        exchange: str,
        trading_dates: Sequence[str | date],
        *,
        coverage_start: str | date | None = None,
        coverage_end: str | date | None = None,
        verified: bool = False,
    ) -> "TradingCalendar":
        parsed = frozenset(_coerce_date(item, "trading_date") for item in trading_dates)
        if not parsed and (coverage_start is None or coverage_end is None):
            raise ValueError("empty calendar requires explicit coverage bounds")
        start = (
            _coerce_date(coverage_start, "coverage_start")
            if coverage_start is not None
            else min(parsed)
        )
        end = (
            _coerce_date(coverage_end, "coverage_end")
            if coverage_end is not None
            else max(parsed)
        )
        return cls(exchange.upper(), parsed, start, end, verified)

    def count_between(self, start: date, end: date) -> int | None:
        """Count trading dates after start through end, or None if uncovered."""

        if start < self.coverage_start or end > self.coverage_end:
            return None
        return sum(start < item <= end for item in self.trading_dates)


@dataclass(frozen=True)
class ContractBar:
    commodity_code: str
    name_cn: str
    exchange: str
    provider_market_id: str
    quote_unit: str
    trade_date: date
    contract_code: str
    contract_month: date
    last_trade_date: date
    open: float
    high: float
    low: float
    close: float
    settlement: float
    pre_settlement: float | None
    volume: int
    open_interest: int
    is_trading: bool = True

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "ContractBar":
        commodity_code = str(row.get("commodity_code", "")).upper()
        if commodity_code not in COMMODITY_SPECS:
            raise MarketDataError(f"unsupported commodity_code: {commodity_code!r}")
        spec = COMMODITY_SPECS[commodity_code]
        exchange = str(row.get("exchange", ""))
        if exchange != spec["exchange"]:
            raise MarketDataError(
                f"{commodity_code} must use {spec['exchange']}, got {exchange!r}"
            )
        declared_currency = row.get("currency")
        if declared_currency is not None and str(declared_currency) != "CNY":
            raise MarketDataError(
                f"{commodity_code} must use CNY, got {declared_currency!r}"
            )
        declared_unit = row.get("quote_unit")
        if declared_unit is not None and str(declared_unit) != spec["quote_unit"]:
            raise MarketDataError(
                f"{commodity_code} must use {spec['quote_unit']}, "
                f"got {declared_unit!r}"
            )
        declared_market = row.get("provider_market_id")
        if (
            declared_market is not None
            and str(declared_market) != spec["provider_market_id"]
        ):
            raise MarketDataError(
                f"{commodity_code} must use provider_market_id "
                f"{spec['provider_market_id']}, got {declared_market!r}"
            )
        contract_code = str(row.get("contract_code", "")).lower()
        prefix = spec["contract_prefix"]
        if len(contract_code) != len(prefix) + 4 or not contract_code.startswith(prefix):
            raise MarketDataError(f"invalid {commodity_code} contract_code: {contract_code!r}")
        suffix = contract_code[-4:]
        if not suffix.isdigit():
            raise MarketDataError(f"invalid contract month in {contract_code!r}")
        year = 2000 + int(suffix[:2])
        month = int(suffix[2:])
        if month < 1 or month > 12:
            raise MarketDataError(f"invalid contract month in {contract_code!r}")
        contract_month = date(year, month, 1)
        declared_month = str(row.get("contract_month", f"{year:04d}-{month:02d}"))
        if declared_month != f"{year:04d}-{month:02d}":
            raise MarketDataError(
                f"contract_month does not match {contract_code!r}: {declared_month!r}"
            )

        def required_date(key: str) -> date:
            value = row.get(key)
            if isinstance(value, date) and not isinstance(value, datetime):
                return value
            if not isinstance(value, str):
                raise MarketDataError(f"missing {key} for {contract_code}")
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise MarketDataError(f"invalid {key}: {value!r}") from exc

        def required_number(key: str) -> float:
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise MarketDataError(f"missing or non-numeric {key} for {contract_code}")
            value = float(value)
            if not math.isfinite(value) or value <= 0:
                raise MarketDataError(f"invalid {key} for {contract_code}: {value}")
            return value

        def required_integer(key: str) -> int:
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise MarketDataError(f"invalid {key} for {contract_code}: {value!r}")
            return value

        trade_date = required_date("trade_date")
        last_trade_date = required_date("last_trade_date")
        if last_trade_date < trade_date:
            raise MarketDataError(f"last_trade_date precedes trade_date for {contract_code}")
        pre_settlement = required_number("pre_settlement")
        is_trading = bool(row.get("is_trading", True))
        open_price = required_number("open")
        high_price = required_number("high")
        low_price = required_number("low")
        close_price = required_number("close")
        settlement_price = required_number("settlement")
        if low_price > high_price:
            raise MarketDataError(f"low exceeds high for {contract_code}")
        if not low_price <= open_price <= high_price:
            raise MarketDataError(f"open falls outside low/high for {contract_code}")
        if not low_price <= close_price <= high_price:
            raise MarketDataError(f"close falls outside low/high for {contract_code}")
        return cls(
            commodity_code=commodity_code,
            name_cn=spec["name_cn"],
            exchange=exchange,
            provider_market_id=spec["provider_market_id"],
            quote_unit=spec["quote_unit"],
            trade_date=trade_date,
            contract_code=contract_code,
            contract_month=contract_month,
            last_trade_date=last_trade_date,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            settlement=settlement_price,
            pre_settlement=pre_settlement,
            volume=required_integer("volume"),
            open_interest=required_integer("open_interest"),
            is_trading=is_trading,
        )


def _record_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "FGCMD-" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20].upper()


def _weekdays_between(start: date, end: date) -> int:
    """Count Monday-Friday dates after start and through end.

    This is an offline fallback for isolated tests. Production adapters must
    supply an official exchange calendar before records can enter Canonical.
    """

    if end <= start:
        return 0
    count = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def _month_key(value: date) -> tuple[int, int]:
    return value.year, value.month


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _candidate_sort_key(bar: ContractBar) -> tuple[int, int, tuple[int, int]]:
    return (-bar.open_interest, -bar.volume, _month_key(bar.contract_month))


def _days_to_expiry(
    bar: ContractBar,
    trade_date: date,
    trading_calendar: TradingCalendar | None,
) -> int:
    if trading_calendar is not None:
        calendar_days = trading_calendar.count_between(
            trade_date, bar.last_trade_date
        )
        if calendar_days is not None:
            return calendar_days
    return _weekdays_between(trade_date, bar.last_trade_date)


def _eligible(
    bar: ContractBar,
    trade_date: date,
    rule: RollRule,
    trading_calendar: TradingCalendar | None,
) -> bool:
    return (
        bar.is_trading
        and bar.last_trade_date >= trade_date
        and _days_to_expiry(bar, trade_date, trading_calendar)
        >= rule.min_days_to_expiry
    )


_PROVENANCE_REQUIRED = {
    "source_id",
    "source_url",
    "provider",
    "retrieved_at",
    "snapshot_id",
    "content_sha256",
    "adapter_version",
    "license_scope",
}
_PROVENANCE_OPTIONAL = {"display_allowed", "redistribution_allowed"}
_LICENSE_SCOPES = {
    "unknown",
    "internal_research",
    "internal_training",
    "redistributable",
}


def _validate_provenance(value: Mapping[str, Any]) -> dict[str, Any]:
    provenance = dict(value)
    missing = _PROVENANCE_REQUIRED - provenance.keys()
    extra = provenance.keys() - _PROVENANCE_REQUIRED - _PROVENANCE_OPTIONAL
    if missing:
        raise MarketDataError(
            f"provenance is missing required fields: {sorted(missing)}"
        )
    if extra:
        raise MarketDataError(f"unsupported provenance fields: {sorted(extra)}")
    if not str(provenance["source_url"]).startswith("https://"):
        raise MarketDataError("provenance.source_url must use HTTPS")
    retrieved_at = str(provenance["retrieved_at"])
    try:
        parsed_retrieved_at = datetime.fromisoformat(
            retrieved_at.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise MarketDataError("provenance.retrieved_at must be ISO 8601") from exc
    if parsed_retrieved_at.tzinfo is None:
        raise MarketDataError("provenance.retrieved_at must include a timezone")
    content_sha256 = str(provenance["content_sha256"])
    if (
        len(content_sha256) != 64
        or content_sha256.lower() != content_sha256
        or any(character not in "0123456789abcdef" for character in content_sha256)
    ):
        raise MarketDataError(
            "provenance.content_sha256 must be 64 lowercase hexadecimal characters"
        )
    if provenance["license_scope"] not in _LICENSE_SCOPES:
        raise MarketDataError("unsupported provenance.license_scope")
    for key in ("source_id", "provider", "snapshot_id", "adapter_version"):
        if not isinstance(provenance[key], str) or not provenance[key].strip():
            raise MarketDataError(f"provenance.{key} must be a non-empty string")
    for key in _PROVENANCE_OPTIONAL:
        if key in provenance and not isinstance(provenance[key], bool):
            raise MarketDataError(f"provenance.{key} must be boolean")
    return provenance


def _commodity_payload(bar: ContractBar) -> dict[str, str]:
    return {
        "commodity_code": bar.commodity_code,
        "name_cn": bar.name_cn,
        "exchange": bar.exchange,
        "provider_market_id": bar.provider_market_id,
        "currency": "CNY",
        "quote_unit": bar.quote_unit,
    }


def _quality_payload(
    provenance: Mapping[str, Any],
    flags: Iterable[str] = (),
) -> dict[str, Any]:
    combined = list(flags)
    if provenance["license_scope"] == "unknown":
        combined.append("LICENSE_SCOPE_UNKNOWN")
    unique_flags = list(dict.fromkeys(combined))
    return {
        "status": "review_required" if unique_flags else "accepted",
        "flags": unique_flags,
    }


def _derived_quality(
    provenance: Mapping[str, Any],
    trading_calendar: TradingCalendar | None,
    bars: Sequence[ContractBar],
) -> dict[str, Any]:
    flags: list[str] = []
    if trading_calendar is None:
        flags.append("OFFICIAL_TRADING_CALENDAR_MISSING")
    else:
        if not trading_calendar.verified:
            flags.append("TRADING_CALENDAR_UNVERIFIED")
        if any(
            trading_calendar.count_between(
                bar.trade_date, bar.last_trade_date
            )
            is None
            for bar in bars
        ):
            flags.append("TRADING_CALENDAR_INCOMPLETE")
    return _quality_payload(provenance, flags)


def _decision_cutoff(signal_date: date) -> str:
    # Daily source data has no intraday publication timestamp. This normalized
    # China-time day boundary states that no later calendar date was used.
    return f"{signal_date.isoformat()}T23:59:59+08:00"


def build_contract_daily_record(
    row: Mapping[str, Any] | ContractBar,
    *,
    provenance: Mapping[str, Any],
    revision: int = 1,
    is_latest: bool = True,
    quality_flags: Iterable[str] = (),
) -> dict[str, Any]:
    """Create a schema-valid auditable contract_daily record."""

    if revision < 1:
        raise MarketDataError("revision must be positive")
    bar = row if isinstance(row, ContractBar) else ContractBar.from_mapping(row)
    validated_provenance = _validate_provenance(provenance)
    flags = list(quality_flags)
    if not bar.low <= bar.settlement <= bar.high:
        flags.append("SETTLEMENT_OUTSIDE_LOW_HIGH")
    payload = {
        "schema_version": "fingoose-commodity-market-v0.2",
        "record_type": "contract_daily",
        "commodity": _commodity_payload(bar),
        "trade_date": bar.trade_date.isoformat(),
        "contract_code": bar.contract_code,
        "contract_month": bar.contract_month.strftime("%Y-%m"),
        "last_trade_date": bar.last_trade_date.isoformat(),
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "settlement": bar.settlement,
        "pre_settlement": bar.pre_settlement,
        "volume": bar.volume,
        "open_interest": bar.open_interest,
        "is_trading": bar.is_trading,
        "revision": revision,
        "is_latest": is_latest,
        "provenance": validated_provenance,
    }
    return {
        **payload,
        "record_id": _record_id(payload),
        "quality": _quality_payload(validated_provenance, flags),
    }


def _event_payload(
    commodity: ContractBar,
    series_id: str,
    rule: RollRule,
    signal_date: date,
    effective_date: date,
    old_contract: str | None,
    new_bar: ContractBar,
    old_bar: ContractBar | None,
    confirmation_days: int,
    reason: str,
    is_forced: bool,
    provenance: Mapping[str, Any],
    quality: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "fingoose-commodity-market-v0.2",
        "record_type": "roll_event",
        "commodity": _commodity_payload(commodity),
        "series_id": series_id,
        "rule_version": rule.version,
        "signal_date": signal_date.isoformat(),
        "effective_date": effective_date.isoformat(),
        "old_contract": old_contract,
        "new_contract": new_bar.contract_code,
        "old_open_interest": old_bar.open_interest if old_bar else None,
        "new_open_interest": new_bar.open_interest,
        "old_volume": old_bar.volume if old_bar else None,
        "new_volume": new_bar.volume,
        "confirmation_days": confirmation_days,
        "reason": reason,
        "is_forced": is_forced,
        "decision_cutoff": _decision_cutoff(signal_date),
        "provenance": dict(provenance),
    }
    return {
        **payload,
        "record_id": _record_id(payload),
        "quality": dict(quality),
    }


def build_continuous_series(
    rows: Iterable[Mapping[str, Any] | ContractBar],
    *,
    provenance: Mapping[str, Any],
    rule: RollRule | None = None,
    vendor_main: Mapping[date | str, Mapping[str, Any]] | None = None,
    trading_calendar: TradingCalendar | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build an OI-selected continuous series and its roll-event audit trail."""

    rule = rule or RollRule()
    bars = [
        item if isinstance(item, ContractBar) else ContractBar.from_mapping(item)
        for item in rows
    ]
    if not bars:
        raise MarketDataError("at least one contract bar is required")
    commodity_codes = {bar.commodity_code for bar in bars}
    if len(commodity_codes) != 1:
        raise MarketDataError("one continuous series cannot mix commodity codes")
    commodity_code = next(iter(commodity_codes))
    expected_exchange = COMMODITY_SPECS[commodity_code]["exchange"]
    if (
        trading_calendar is not None
        and trading_calendar.exchange != expected_exchange
    ):
        raise MarketDataError(
            f"{commodity_code} requires a {expected_exchange} trading calendar"
        )
    validated_provenance = _validate_provenance(provenance)
    derived_quality = _derived_quality(
        validated_provenance, trading_calendar, bars
    )
    by_day: dict[date, dict[str, ContractBar]] = {}
    for bar in bars:
        day = by_day.setdefault(bar.trade_date, {})
        if bar.contract_code in day:
            raise MarketDataError(
                f"duplicate contract bar: {bar.contract_code} {bar.trade_date}"
            )
        day[bar.contract_code] = bar

    dates = sorted(by_day)
    series_id = f"FINGOOSE-{commodity_code}-OI-MAIN-V1"
    active: str | None = None
    pending: tuple[date, str, str, str, bool, int] | None = None
    prior_candidate: str | None = None
    advantage_streak = 0
    events: list[dict[str, Any]] = []
    continuous: list[dict[str, Any]] = []
    previous_settlement_index: float | None = None
    previous_close_index: float | None = None

    for index, current_date in enumerate(dates):
        day_bars = by_day[current_date]
        eligible = [
            bar for bar in day_bars.values() if _eligible(bar, current_date, rule, trading_calendar)
        ]
        if active is None:
            if not eligible:
                raise MarketDataError(
                    f"no eligible contract on initialization date {current_date}"
                )
            chosen = sorted(eligible, key=_candidate_sort_key)[0]
            active = chosen.contract_code
            events.append(
                _event_payload(
                    chosen,
                    series_id,
                    rule,
                    current_date,
                    current_date,
                    None,
                    chosen,
                    None,
                    0,
                    "INIT",
                    False,
                    validated_provenance,
                    derived_quality,
                )
            )

        effective_event: dict[str, Any] | None = None
        if pending is not None:
            (
                signal_date,
                old_code,
                new_code,
                reason,
                is_forced,
                confirmation_days,
            ) = pending
            new_effective_bar = day_bars.get(new_code)
            if new_effective_bar is None or not new_effective_bar.is_trading:
                raise MarketDataError(
                    f"new contract {new_code} has no valid bar on effective date "
                    f"{current_date}"
                )
            signal_bars = by_day[signal_date]
            old_signal_bar = signal_bars.get(old_code)
            new_signal_bar = signal_bars.get(new_code)
            if old_signal_bar is None or new_signal_bar is None:
                raise MarketDataError(
                    "roll signal cannot be reproduced from signal-date bars"
                )
            effective_event = _event_payload(
                new_signal_bar,
                series_id,
                rule,
                signal_date,
                current_date,
                old_code,
                new_signal_bar,
                old_signal_bar,
                confirmation_days,
                reason,
                is_forced,
                validated_provenance,
                derived_quality,
            )
            events.append(effective_event)
            active = new_code
            pending = None
            prior_candidate = None
            advantage_streak = 0

        current_bar = day_bars.get(active)
        if current_bar is None:
            raise MarketDataError(f"active contract unavailable on {current_date}")
        if not current_bar.is_trading:
            raise MarketDataError(f"active contract is not trading on {current_date}")

        # Signals use only current-close information and take effect next date.
        forward_candidates = [
            bar
            for bar in eligible
            if _month_key(bar.contract_month)
            > _month_key(current_bar.contract_month)
        ]
        candidate = (
            sorted(forward_candidates, key=_candidate_sort_key)[0]
            if forward_candidates
            else None
        )
        needs_forced_roll = not _eligible(current_bar, current_date, rule, trading_calendar)
        if needs_forced_roll:
            if candidate is None:
                raise MarketDataError(
                    f"no forward eligible contract for forced roll on {current_date}"
                )
            if index + 1 < len(dates):
                pending = (
                    current_date,
                    current_bar.contract_code,
                    candidate.contract_code,
                    "FORCED_EXPIRY",
                    True,
                    0,
                )
            prior_candidate = None
            advantage_streak = 0
        elif candidate is not None and candidate.open_interest > current_bar.open_interest:
            if candidate.contract_code == prior_candidate:
                advantage_streak += 1
            else:
                prior_candidate = candidate.contract_code
                advantage_streak = 1
        else:
            prior_candidate = None
            advantage_streak = 0

        if (
            candidate is not None
            and advantage_streak >= rule.confirmation_days
            and index + 1 < len(dates)
            and pending is None
        ):
            pending = (
                current_date,
                current_bar.contract_code,
                candidate.contract_code,
                "OI_CONFIRM",
                False,
                rule.confirmation_days,
            )

        if previous_settlement_index is None:
            settlement_return = None
            close_return = None
            settlement_index = 100.0
            close_index = 100.0
        else:
            prior_bar = by_day[dates[index - 1]].get(active)
            if prior_bar is None or not prior_bar.is_trading:
                raise MarketDataError(
                    f"missing prior-day bar for active contract {active} on "
                    f"{current_date}"
                )
            settlement_return = (
                current_bar.settlement / prior_bar.settlement - 1.0
            )
            close_return = current_bar.close / prior_bar.close - 1.0
            settlement_index = previous_settlement_index * (
                1.0 + settlement_return
            )
            close_index = previous_close_index * (1.0 + close_return)

        vendor_value = None
        if vendor_main:
            vendor_value = vendor_main.get(current_date) or vendor_main.get(
                current_date.isoformat()
            )
        payload = {
            "schema_version": "fingoose-commodity-market-v0.2",
            "record_type": "continuous_daily",
            "commodity": _commodity_payload(current_bar),
            "trade_date": current_date.isoformat(),
            "series_id": series_id,
            "rule_version": rule.version,
            "active_contract": active,
            "is_roll_effective_date": (
                effective_event is not None
                and effective_event["effective_date"] == current_date.isoformat()
            ),
            "old_contract": (
                effective_event.get("old_contract") if effective_event else None
            ),
            "settlement_return": settlement_return,
            "settlement_index": settlement_index,
            "close_return": close_return,
            "close_index": close_index,
            "basis_disagreement": False,
            "vendor_main": vendor_value,
            "provenance": dict(validated_provenance),
        }
        continuous.append(
            {
                **payload,
                "record_id": _record_id(payload),
                "quality": dict(derived_quality),
            }
        )
        previous_settlement_index = settlement_index
        previous_close_index = close_index

    return continuous, events


def _basis_result(
    bars: list[dict[str, Any]],
    basis: str,
    as_of: date,
    target_calendar_date: date,
    rule: RollRule,
) -> dict[str, Any]:
    if any(item.get(basis) is None for item in bars):
        raise MarketDataError(f"{basis} is required for basis comparison")
    prior = [
        item for item in bars if date.fromisoformat(item["trade_date"]) <= as_of
    ]
    if not prior or date.fromisoformat(prior[-1]["trade_date"]) != as_of:
        raise MarketDataError(f"as_of_date must have a valid {basis}")

    log_returns: list[float] = []
    for left, right in zip(prior, prior[1:]):
        if left[basis] <= 0 or right[basis] <= 0:
            raise MarketDataError(f"{basis} must be positive")
        log_returns.append(math.log(right[basis] / left[basis]))
    if len(log_returns) < 60:
        raise MarketDataError("at least 60 pre-cutoff log returns are required")
    last_60 = log_returns[-60:]
    sigma_annual = statistics.stdev(last_60) * math.sqrt(
        rule.annualization_days
    )
    if sigma_annual <= 0 or not math.isfinite(sigma_annual):
        raise MarketDataError("pre-cutoff volatility must be positive")

    future = [
        item
        for item in bars
        if date.fromisoformat(item["trade_date"]) > as_of
        and date.fromisoformat(item["trade_date"]) >= target_calendar_date
    ]
    if not future:
        raise MarketDataError("three-month result date is missing")
    target = future[0]
    target_date = date.fromisoformat(target["trade_date"])
    future_days = [
        item
        for item in bars
        if as_of < date.fromisoformat(item["trade_date"]) <= target_date
    ]
    future_log_return = math.log(target[basis] / prior[-1][basis])
    z = future_log_return / (
        sigma_annual
        * math.sqrt(len(future_days) / rule.annualization_days)
    )
    if z >= rule.z_threshold:
        outcome = "UP"
    elif z <= -rule.z_threshold:
        outcome = "DOWN"
    else:
        outcome = "NOISE"
    return {
        "basis": basis,
        "target_date": target["trade_date"],
        "pre_cutoff_observations": len(last_60),
        "future_trading_days": len(future_days),
        "sigma_annual": sigma_annual,
        "future_log_return": future_log_return,
        "z": z,
        "outcome": outcome,
    }


def validate_three_month_forecast(
    continuous: Iterable[Mapping[str, Any]],
    as_of_date: str | date,
    *,
    rule: RollRule | None = None,
) -> dict[str, Any]:
    """Calculate 60-day volatility and two-basis three-month outcomes."""

    rule = rule or RollRule()
    as_of = (
        date.fromisoformat(as_of_date)
        if isinstance(as_of_date, str)
        else as_of_date
    )
    bars = sorted(
        [dict(item) for item in continuous], key=lambda item: item["trade_date"]
    )
    if not bars:
        raise MarketDataError("continuous series is empty")

    target_calendar_date = _add_months(as_of, rule.horizon_months)
    settlement = _basis_result(
        bars, "settlement_index", as_of, target_calendar_date, rule
    )
    close = _basis_result(
        bars, "close_index", as_of, target_calendar_date, rule
    )
    basis_disagreement = settlement["outcome"] != close["outcome"]
    return {
        "as_of_date": as_of.isoformat(),
        "target_date": settlement["target_date"],
        "pre_cutoff_observations": settlement["pre_cutoff_observations"],
        "future_trading_days": settlement["future_trading_days"],
        "sigma_annual": settlement["sigma_annual"],
        "future_log_return": settlement["future_log_return"],
        "z": settlement["z"],
        "outcome": settlement["outcome"],
        "label": {
            "UP": "BULLISH",
            "DOWN": "BEARISH",
            "NOISE": "UNCERTAIN",
        }[settlement["outcome"]],
        "settlement_basis": settlement,
        "close_basis": close,
        "basis_disagreement": basis_disagreement,
        "quality_status": (
            "review_required" if basis_disagreement else "accepted"
        ),
        "quality_flags": (
            ["CLOSE_SETTLEMENT_OUTCOME_CONFLICT"]
            if basis_disagreement
            else []
        ),
    }
