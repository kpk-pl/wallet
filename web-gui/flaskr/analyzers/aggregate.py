from itertools import groupby
from enum import Enum
from decimal import Decimal
from typing import List

from flaskr import typing
from flaskr.model import (
    Asset,
    AggregatedAsset,
    AssetOperation,
    AssetOperationType,
    AssetType,
    WalletAsset,
)


class AggregationType(str, Enum):
    pricing = 'p'
    name = 'n'


def _idsOf(entry: WalletAsset):
    if isinstance(entry, AggregatedAsset):
        return list(entry.ids)
    return [entry.id]


def _institutionsOf(entry: WalletAsset):
    if isinstance(entry, AggregatedAsset):
        return list(entry.institutions)
    return [entry.institution]


def _key(aggregationType: AggregationType):
    # Pydantic v1 BaseModel is not orderable/hashable by default, so we use
    # repr() as a stable, sortable, hashable representative. Pydantic's repr
    # lists fields in declaration order and ObjectId has a stable repr, so
    # equal models yield equal reprs.
    if aggregationType == AggregationType.pricing:
        return lambda e: (
            repr(e.pricing) if e.pricing is not None else 'null',
            repr(e.currency),
        )
    if aggregationType == AggregationType.name:
        return lambda e: (e.name, repr(e.currency))
    raise ValueError(f"Unknown aggregation type {aggregationType}")


def _shouldAggregate(aggregationType: AggregationType, entry: WalletAsset) -> bool:
    # 'name' aggregation only operates on entries without pricing (deposits).
    # Entries with pricing pass straight through — they are grouped by 'p' instead.
    if aggregationType == AggregationType.name:
        return entry.pricing is None
    return True


def _renamespacedOps(entry: WalletAsset) -> List[AssetOperation]:
    # AggregatedAsset operations were namespaced on a prior merge — pass through (still copied).
    if isinstance(entry, AggregatedAsset):
        return [op.copy() for op in entry.operations]

    prefix = f"{entry.institution}:"
    return [
        op.copy(update={'orderId': prefix + op.orderId}) if op.orderId else op.copy()
        for op in entry.operations
    ]


def _merge(lhs: WalletAsset, rhs: WalletAsset) -> AggregatedAsset:
    # The grouping key already enforced these; the asserts trap any future regression.
    assert lhs.currency == rhs.currency
    assert lhs.pricing == rhs.pricing

    ids = sorted(set(_idsOf(lhs) + _idsOf(rhs)), key=str)
    institutions = sorted(set(_institutionsOf(lhs) + _institutionsOf(rhs)))

    mergedOps = sorted(_renamespacedOps(lhs) + _renamespacedOps(rhs), key=lambda op: op.date)

    isDeposit = lhs.type == AssetType.deposit
    finalQuantity = Decimal(0)
    recomputed: List[AssetOperation] = []
    for op in mergedOps:
        if op.type == AssetOperationType.earning:
            if isDeposit and op.quantity is not None:
                finalQuantity = finalQuantity + op.quantity
        elif op.quantity is not None:
            finalQuantity = typing.Operation.adjustQuantity(op.type, finalQuantity, op.quantity)
        recomputed.append(op.copy(update={'finalQuantity': finalQuantity}))

    labels = sorted(set(lhs.labels) | set(rhs.labels))

    return AggregatedAsset(
        ids=ids,
        institutions=institutions,
        name=lhs.name,
        ticker=lhs.ticker,
        currency=lhs.currency,
        type=lhs.type,
        category=lhs.category,
        subcategory=lhs.subcategory,
        region=lhs.region,
        pricing=lhs.pricing,
        operations=recomputed,
        labels=labels,
        hasOrderIds=lhs.hasOrderIds,
    )


def aggregate(entries: List[WalletAsset], aggregationType) -> List[WalletAsset]:
    if isinstance(aggregationType, str):
        aggregationType = AggregationType(aggregationType)

    participants = [e for e in entries if _shouldAggregate(aggregationType, e)]
    ignored = [e for e in entries if not _shouldAggregate(aggregationType, e)]

    keyFn = _key(aggregationType)
    participants = sorted(participants, key=keyFn)

    result: List[WalletAsset] = []
    for _, group in groupby(participants, keyFn):
        members = list(group)
        merged = members[0]
        for entry in members[1:]:
            merged = _merge(merged, entry)
        result.append(merged)

    return ignored + result
