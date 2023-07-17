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
                     (v != 0 || parseFloat(asset.profit[i + fromIdx]) != 0) ?
                     utils.float.normalize(v + parseFloat(asset.profit[i + fromIdx]) - parseFloat(asset.investedValue[i + fromIdx])) :
                     null
                 ), options
    );

    const initialValue = parseFloat(asset.value[fromIdx]);
    const initialValueWithProfit = initialValue + parseFloat(asset.profit[fromIdx]);
    const finalValueWithProfit = parseFloat(asset.value[asset.value.length-1]) + parseFloat(asset.profit[asset.value.length-1]);
    const investmentDiff = parseFloat(asset.investedValue[asset.value.length-1]) - parseFloat(asset.investedValue[fromIdx]);
    element.find(".value").html(
      initialValue != 0 ? (((finalValueWithProfit - initialValueWithProfit - investmentDiff) / initialValueWithProfit * 100.0).toFixed(2) + "%") : ""
    ).each(styling.colorGain);
  }
}
