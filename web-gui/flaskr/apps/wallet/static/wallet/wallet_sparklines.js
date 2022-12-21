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
    const element = getter(asset)
    element.find(".sparkline").sparkline(
      asset.value.slice(fromIdx)
                 .map(parseFloat)
                 .map(
                   (v, i) =>
                     (v > 0 || parseFloat(asset.profit[i + fromIdx]) > 0) ?
                     utils.float.normalize(v + parseFloat(asset.profit[i + fromIdx]) - parseFloat(asset.investedValue[i + fromIdx])) :
                     null
                 ), options
    );

    const initialValue = parseFloat(asset.value[fromIdx]) + parseFloat(asset.profit[fromIdx]);
    const finalValue = parseFloat(asset.value[asset.value.length-1]) + parseFloat(asset.profit[asset.value.length-1]);
    element.find(".value").html(
      initialValue != 0 ? (((finalValue - initialValue) / initialValue * 100.0).toFixed(2) + "%") : ""
    ).each(styling.colorGain);
  }
}
