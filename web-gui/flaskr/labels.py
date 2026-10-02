"""Restricted views: limit an app instance to a subset of asset labels.

An instance started with ``ALLOWED_LABELS=a,b`` only shows assets tagged with
at least one of those labels. It is read-only except for recording new
operations on those assets and editing strategies of the allowed labels:
assets and operations cannot be edited, pricing and quotes are hidden, and backup and automatic quote updates
are disabled. Without the variable the app behaves as before.

This is a convenience for sharing a narrower view (e.g. a second port for a
family member). It is not access control: anyone who can reach the
unrestricted instance still sees everything.
"""
from flask import abort, current_app


def parseAllowedLabels(raw):
    """Turn the ``ALLOWED_LABELS`` setting into a sorted list, or None when unset."""
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.split(',')
    labels = sorted({str(label).strip() for label in raw if str(label).strip()})
    return labels or None


def allowedLabels():
    """Labels this instance may show, or None when it is unrestricted."""
    return current_app.config.get('ALLOWED_LABELS')


def isRestricted():
    return allowedLabels() is not None


def isLabelAllowed(label):
    allowed = allowedLabels()
    return allowed is None or label in allowed


def resolveLabel(label):
    """Validate the label filter requested by the user.

    Returns the label to filter by (None means "no label filter"). A label
    outside the allowed set is rejected with 403. A restricted instance with a
    single allowed label always filters by that label.
    """
    if not label:
        label = None

    allowed = allowedLabels()
    if allowed is None:
        return label

    if label is None:
        return allowed[0] if len(allowed) == 1 else None

    if label not in allowed:
        abort(403)

    return label


def assetMatch(label=None):
    """Mongo ``$match`` fragment selecting assets visible under ``label``.

    ``label`` must already be resolved with :func:`resolveLabel`.
    """
    if label is not None:
        return {'labels': label}

    allowed = allowedLabels()
    if allowed is not None:
        return {'labels': {'$in': allowed}}

    return {}


def isAssetVisible(doc):
    allowed = allowedLabels()
    if allowed is None:
        return True
    return bool(set(doc.get('labels') or []) & set(allowed))


def requireAssetVisible(doc):
    """Abort with 404 for an asset this instance must not reveal."""
    if doc is None or not isAssetVisible(doc):
        abort(404)
    return doc


def visibleLabels(labels):
    """Hide labels outside the allowed set when displaying an asset."""
    allowed = allowedLabels()
    labels = list(labels or [])
    if allowed is None:
        return labels
    return [label for label in labels if label in allowed]


def forbidInRestrictedView():
    """Reject an action that a restricted instance does not offer."""
    if isRestricted():
        abort(403)


def hideInRestrictedView():
    """Pretend a whole section does not exist on a restricted instance."""
    if isRestricted():
        abort(404)
