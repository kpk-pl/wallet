# Shared FIFO position matcher.
#
# A single source of truth for matching SELL operations against the BUY/RECEIVE lots they
# close, first-in-first-out, isolated per orderId. Both the profits analyzer (cost basis,
# realised profit, matched-lot display) and the pricing engine (remaining open lots for bond
# valuation, both current and historical) consume this so they can never disagree on which
# lot a sale drew from.
#
# NOTE: operations are matched in the order given (assumed chronological, as stored). This
# module never reorders them, so the result stays index-aligned with the operations list.

from dataclasses import dataclass, field
from collections import defaultdict
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional

import flaskr.model as model


@dataclass
class Lot:
    # The BUY / RECEIVE operation that opened this lot
    operation: model.AssetOperation
    # Index of that operation within the matched operations list
    openIndex: int
    # Quantity the lot opened with
    openedQuantity: Decimal
    # Quantity still open after all sells have drawn from it
    remaining: Decimal


@dataclass
class Match:
    # The lot this drawdown closed against
    lot: Lot
    # Quantity drawn from the lot by the sell
    quantity: Decimal


@dataclass
class SellResult:
    # Index of the SELL operation within the operations list
    sellIndex: int
    operation: model.AssetOperation
    matches: List[Match] = field(default_factory=list)


@dataclass
class MatchResult:
    # Every lot opened, in the order it was opened
    lots: List[Lot] = field(default_factory=list)
    # Lots with remaining > 0, grouped by orderId
    openLotsByOrder: Dict[Optional[str], List[Lot]] = field(default_factory=dict)
    # One entry per SELL operation
    sells: List[SellResult] = field(default_factory=list)
    # Index-aligned to operations: final remaining open quantity for an opening op, else None
    remainingByIndex: List[Optional[Decimal]] = field(default_factory=list)
    # Index-aligned to operations: the SellResult for a sell op, else None
    sellByIndex: List[Optional[SellResult]] = field(default_factory=list)


def _opensLot(operation: model.AssetOperation) -> bool:
    return operation.type in (model.AssetOperationType.buy, model.AssetOperationType.receive)


def match(operations: List[model.AssetOperation], *, strict: bool = True) -> MatchResult:
    """Match SELLs against opening lots FIFO, isolated per orderId.

    When ``strict`` a SELL that cannot be fully matched raises AssertionError (the defensive
    backstop expected by the profits analyzer). When not ``strict`` the unmatched remainder is
    silently ignored (the pricing engine tolerates sells beyond the loaded operations)."""
    result = MatchResult()
    result.remainingByIndex = [None] * len(operations)
    result.sellByIndex = [None] * len(operations)

    openLots: Dict[Optional[str], List[Lot]] = defaultdict(list)

    for index, operation in enumerate(operations):
        if _opensLot(operation):
            quantity = operation.quantity
            # A zero-quantity lot carries no cost basis and would divide by zero when drawn
            # from; skip it entirely (also guards against an infinite SELL loop on a 0 lot).
            if quantity is None or quantity == 0:
                continue
            lot = Lot(operation=operation, openIndex=index, openedQuantity=quantity, remaining=quantity)
            result.lots.append(lot)
            openLots[operation.orderId].append(lot)
        elif operation.type is model.AssetOperationType.sell:
            sellResult = SellResult(sellIndex=index, operation=operation)
            result.sells.append(sellResult)
            result.sellByIndex[index] = sellResult

            need = operation.quantity
            bucket = openLots[operation.orderId]
            while need is not None and need > 0 and bucket:
                lot = bucket[0]
                drawn = min(lot.remaining, need)
                sellResult.matches.append(Match(lot=lot, quantity=drawn))
                lot.remaining -= drawn
                need -= drawn
                if lot.remaining == 0:
                    bucket.pop(0)

            if strict:
                assert need == 0, f"SELL of {operation.quantity} could not be fully matched (orderId={operation.orderId})"

    for lot in result.lots:
        result.remainingByIndex[lot.openIndex] = lot.remaining

    # A SELL touches openLots[orderId] (a defaultdict) even when nothing was ever opened for
    # that order, leaving an empty bucket behind; drop those so sell-only orders don't appear.
    result.openLotsByOrder = {
        orderId: remaining
        for orderId, lots in openLots.items()
        if (remaining := [lot for lot in lots if lot.remaining > 0])
    }

    return result


def openQuantityOverTime(result: MatchResult, lot: Lot, timescale: List[datetime]) -> List[Decimal]:
    """Reconstruct ``lot``'s open quantity at each point in ``timescale``.

    The lot holds zero before it is opened, jumps to its opened quantity at the first timescale
    point at or after the opening op's date, then steps down by each matched quantity from the
    first timescale point strictly after the closing sell's date. Sells dated at or after the
    end of the timescale leave the series unchanged (matching historical pricing behaviour)."""
    # Before the lot was opened it held nothing; only points on/after the open date carry it.
    series = [lot.openedQuantity if date >= lot.operation.date else Decimal(0) for date in timescale]

    for sell in result.sells:
        for match_ in sell.matches:
            if match_.lot is not lot:
                continue
            firstIdx = next((idx for idx, date in enumerate(timescale) if date > sell.operation.date), None)
            if firstIdx is None:
                continue
            for idx in range(firstIdx, len(timescale)):
                series[idx] -= match_.quantity

    return series
