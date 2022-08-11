function updateSparklines(historicalData, months, getter) {
  const options = {
    type: 'line',
    width: '100',
    spotColor: false,
    minSpotColor: false,
    maxSpotColor: false
  };

  const timeRange = moment().subtract(months, 'months');
  const fromIdx = historicalData.t.findIndex(t => new Date(t) >= timeRange)

  for (let asset of historicalData.assets) {
    getter(asset).sparkline(
      asset.value.slice(fromIdx)
                 .map(parseFloat)
                 .map(
                   (v, i) =>
                     (v > 0 || parseFloat(asset.profit[i + fromIdx]) > 0) ?
                     utils.float.normalize(v + parseFloat(asset.profit[i + fromIdx]) - parseFloat(asset.investedValue[i + fromIdx])) :
                     null
                 ), options
    );
  }
}
