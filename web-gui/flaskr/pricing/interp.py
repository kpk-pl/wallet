from decimal import Decimal
from flaskr.model import QuoteHistoryItem
from datetime import datetime
from typing import List


# based on the quote info from 'data' performs linear interpolation to fill all
# timepoints in 'timeScale'. If there is no quote available for some of the leftmost
# points in the 'timeScale', uses 'leftFill'. If 'leftFill' is None then uses next available
# quote from the future. The same applies for 'rightFill' on the right side
def interp(data:List[QuoteHistoryItem], timeScale:List[datetime], leftFill = None, rightFill = None):
    if len(timeScale) == 0:
        return []

    assert len(data) > 0

    if leftFill is not None and not isinstance(leftFill, Decimal):
        leftFill = Decimal(leftFill)

    if rightFill is not None and not isinstance(rightFill, Decimal):
        rightFill = Decimal(rightFill)

    result = []
    quoteIdx = 0

    for dateIdx in timeScale:
        thisQuote = data[quoteIdx]
        while thisQuote.timestamp < dateIdx and quoteIdx < len(data) - 1:
            quoteIdx += 1
            thisQuote = data[quoteIdx]

        if quoteIdx == 0:
            result.append(QuoteHistoryItem(timestamp=dateIdx, quote = data[0].quote if leftFill is None else leftFill))
        elif thisQuote.timestamp < dateIdx:
            result.append(QuoteHistoryItem(timestamp=dateIdx, quote = data[-1].quote if rightFill is None else rightFill))
        else:
            prevQuote = data[quoteIdx-1]
            timeTillNow = Decimal(dateIdx.timestamp() - prevQuote.timestamp.timestamp())
            timeBetweenPoints = Decimal(thisQuote.timestamp.timestamp() - prevQuote.timestamp.timestamp())
            linearCoef = timeTillNow / timeBetweenPoints
            linearQuote = linearCoef * (thisQuote.quote - prevQuote.quote) + prevQuote.quote
            result.append(QuoteHistoryItem(timestamp=dateIdx, quote=linearQuote))

    return result
