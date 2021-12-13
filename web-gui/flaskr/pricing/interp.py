# based on the quote info from 'data' performs linear interpolation to fill all
# timepoints in 'timeScale'. If there is no quote available for some of the leftmost
# points in the 'timeScale', uses 'leftFill'. If 'leftFill' is None then uses next available
# quote from the future. The same applies for 'rightFill' on the right side
def interp(data, timeScale, leftFill = None, rightFill = None):
    assert len(data) > 0

    result = []
    quoteIdx = 0

    for dateIdx in timeScale:
        thisQuote = data[quoteIdx]
        while thisQuote['timestamp'] < dateIdx and quoteIdx < len(data) - 1:
            quoteIdx += 1
            thisQuote = data[quoteIdx]

        if quoteIdx == 0:
            result.append({'timestamp': dateIdx, 'quote': data[0]['quote'] if leftFill is None else leftFill})
        elif thisQuote['timestamp'] < dateIdx:
            result.append({'timestamp': dateIdx, 'quote': data[-1]['quote'] if rightFill is None else rightFill})
        else:
            prevQuote = data[quoteIdx-1]
            linearCoef = (dateIdx.timestamp() - prevQuote['timestamp'].timestamp())/(thisQuote['timestamp'].timestamp() - prevQuote['timestamp'].timestamp())
            linearQuote = linearCoef * (thisQuote['quote'] - prevQuote['quote']) + prevQuote['quote']
            result.append({'timestamp': dateIdx, 'quote': linearQuote})

    return result
