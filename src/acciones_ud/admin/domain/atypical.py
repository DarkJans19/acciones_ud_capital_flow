"""RF-45/H7: deterministic signals; a signal never restricts an account."""

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import timedelta
from decimal import Decimal, localcontext
from itertools import groupby

from acciones_ud.admin.domain.model import AtypicalFlag, BehaviorEvent, LedgerExecution, Raw

RULES_VERSION = "atypical-v2"


@dataclass(frozen=True)
class AtypicalConfig:
    absolute_usd: Decimal = Decimal("10000.00")
    multiplier: Decimal = Decimal(3)
    window_days: int = 90
    min_history: int = 5
    frequency_count: int = 20
    frequency_seconds: int = 300
    cancellation_count: int = 10
    cancellation_seconds: int = 300
    rejection_count: int = 5
    rejection_seconds: int = 3600


def flag(executions: list[LedgerExecution], config: AtypicalConfig) -> list[AtypicalFlag]:
    history: dict[object, deque[LedgerExecution]] = defaultdict(deque)
    sums: dict[object, Decimal] = defaultdict(Decimal)
    result = []
    with localcontext() as ctx:
        ctx.prec = 60
        # Batch equal instants: neither input order nor execution IDs affect baselines.
        for at, group in groupby(
            sorted(executions, key=lambda e: e.executed_at), key=lambda e: e.executed_at
        ):
            batch = list(group)
            for e in batch:
                window = history[e.user_id]
                while window and window[0].executed_at < at - timedelta(days=config.window_days):
                    old = window.popleft()
                    sums[e.user_id] -= old.qty * old.price
                amount, reasons = e.qty * e.price, []
                mean = sums[e.user_id] / len(window) if window else None
                if amount >= config.absolute_usd:
                    reasons.append("absolute_threshold")
                if (
                    mean is not None
                    and len(window) >= config.min_history
                    and amount > config.multiplier * mean
                ):
                    reasons.append("relative_to_history")
                if reasons:
                    result.append(
                        AtypicalFlag(
                            e.execution_id,
                            e.user_id,
                            at,
                            tuple(reasons),
                            {
                                "gross_amount": amount,
                                "baseline_mean": mean,
                                "baseline_count": len(window),
                                "symbol": e.symbol,
                                "market": e.exchange,
                                "side": e.side,
                                "order_id": e.order_id,
                            },
                            (e.execution_id,),
                            configuration=asdict(config),
                        )
                    )
            for e in batch:
                history[e.user_id].append(e)
                sums[e.user_id] += e.qty * e.price
    return sorted(result, key=lambda f: (f.at, f.event_id))


def behavior_flags(events: list[BehaviorEvent], config: AtypicalConfig) -> list[AtypicalFlag]:
    users: dict[object, list[BehaviorEvent]] = defaultdict(list)
    for event in events:
        users[event.user_id].append(event)
    result = []
    for values in users.values():
        windows: dict[str, deque[BehaviorEvent]] = defaultdict(deque)
        rejection_run: deque[BehaviorEvent] = deque()
        for at, group in groupby(sorted(values, key=lambda e: (e.at, e.id)), key=lambda e: e.at):
            batch = list(group)
            for kind, seconds, threshold, rule in (
                ("created", config.frequency_seconds, config.frequency_count, "order_frequency"),
                (
                    "canceled",
                    config.cancellation_seconds,
                    config.cancellation_count,
                    "cancellation_frequency",
                ),
            ):
                current = [e for e in batch if e.kind == kind]
                window = windows[kind]
                while window and window[0].at <= at - timedelta(seconds=seconds):
                    window.popleft()
                window.extend(current)
                if current and len({e.order_id for e in window}) >= threshold:
                    for event in current:
                        result.append(
                            AtypicalFlag(
                                event.id,
                                event.user_id,
                                at,
                                (rule,),
                                {
                                    "count": len({e.order_id for e in window}),
                                    "threshold": threshold,
                                    "window_seconds": seconds,
                                },
                                tuple(e.id for e in window),
                                configuration=asdict(config),
                            )
                        )
            terminal = [e for e in batch if e.kind in {"rejected", "failed", "accepted"}]
            # Mixed outcomes at one instant break the run conservatively.
            if any(e.kind != "rejected" or not e.user_rejection for e in terminal):
                rejection_run.clear()
                continue
            while rejection_run and rejection_run[0].at <= at - timedelta(
                seconds=config.rejection_seconds
            ):
                rejection_run.popleft()
            rejection_run.extend(terminal)
            if terminal and len({e.order_id for e in rejection_run}) >= config.rejection_count:
                for event in terminal:
                    observed: Raw = {
                        "count": len({e.order_id for e in rejection_run}),
                        "threshold": config.rejection_count,
                        "window_seconds": config.rejection_seconds,
                    }
                    result.append(
                        AtypicalFlag(
                            event.id,
                            event.user_id,
                            at,
                            ("repeated_rejections",),
                            observed,
                            tuple(e.id for e in rejection_run),
                            configuration=asdict(config),
                        )
                    )
    return sorted(result, key=lambda f: (f.at, f.event_id, f.reasons))
