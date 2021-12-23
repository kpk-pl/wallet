function assetChangeSparklines(historicalData, months, getter) {
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
      asset.value.slice(fromIdx).map((v, i) => v > 0 ? utils.float.normalize(v - asset.investedValue[i + fromIdx]) : null),
      options
    );
  }
}
