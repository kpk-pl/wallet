var apexAssetAllocationCharts = Object.create(null);

$(function(){
  function options(type) {
    return jQuery.extend(true, {}, apexOptions, {
      chart: {
        stacked: ['value', 'investment', 'share'].includes(type)
      },
      stroke: {
        width: ['value', 'investment', 'share'].includes(type) ? 0 : undefined
      },
      yaxis: {
        decimalsInFloat: (['plpercent'].includes(type) ? 1 : (['share'].includes(type) ? 2 : 0)),
        title: { text: (['plpercent', 'share'].includes(type) ? '%' : 'PLN') }
      },
      fill: {
        opacity: ['summary'].includes(type) ? [0.6, 1] : (['value', 'investment', 'share'].includes(type) ? 1 : undefined)
      }
    });
  }

  for (let type of ['netpl', 'plpercent', 'summary', 'value', 'investment', 'share']) {
    apexAssetAllocationCharts[type] = new ApexCharts(document.getElementById('assetAllocation_chart_' + type), options(type));
    apexAssetAllocationCharts[type].render();
  }
});

function updateAllocationCharts(data){
  function category(asset) {
    if (asset.subcategory)
      return asset.subcategory + ' ' + asset.category;
    return asset.category;
  }

  let mapping = Object.create(null);
  let totals = {
    'value': new Array(data.t.length).fill(0),
    'investment': new Array(data.t.length).fill(0),
    'profit': new Array(data.t.length).fill(0)
  }

  for (let asset of data.assets) {
    const cat = category(asset);
    const assetValue = asset.value.map(parseFloat);
    const assetInvestedValue = asset.investedValue.map(parseFloat);
    const assetProfit = asset.profit.map(parseFloat);

    if (cat in mapping) {
      mapping[cat].value = mapping[cat].value.map((v, i) => v + assetValue[i]);
      mapping[cat].investment = mapping[cat].investment.map((v, i) => v + assetInvestedValue[i]);
      mapping[cat].profit = mapping[cat].profit.map((v, i) => v + assetProfit[i]);
    } else {
      mapping[cat] = {'value': assetValue, 'investment': assetInvestedValue, 'profit': assetProfit};
    }

    totals.value = totals.value.map((v, i) => v + assetValue[i]);
    totals.investment = totals.investment.map((v, i) => v + assetInvestedValue[i]);
    totals.profit = totals.profit.map((v, i) => v + assetProfit[i]);
  }

  for (let category in mapping) {
    apexAssetAllocationCharts.value.appendSeries({
      name: category,
      data: mapping[category].value.map((v, i) => { return {x: data.t[i], y: v}; })
    });
    apexAssetAllocationCharts.investment.appendSeries({
      name: category,
      data: mapping[category].investment.map((v, i) => { return {x: data.t[i], y: v}; })
    });
    apexAssetAllocationCharts.share.appendSeries({
      name: category,
      data: mapping[category].value.map((v, i) => { return {x: data.t[i], y: v/totals.value[i]*100}; })
    });
  }

  apexAssetAllocationCharts.summary.appendSeries({
    name: "Value",
    type: "area",
    data: totals.value.map((v, i) => { return {x: data.t[i], y: v}; })
  });
  apexAssetAllocationCharts.summary.appendSeries({
    name: "Investment",
    type: "line",
    data: totals.investment.map((v, i) => { return {x: data.t[i], y: v}; })
  });

  const netPlAdjust = totals.value[0] + totals.profit[0] - totals.investment[0];
  apexAssetAllocationCharts.netpl.appendSeries({
    name: "Net P/L",
    data: totals.value.map((v, i) => { return {x: data.t[i], y: (v + totals.profit[i] - totals.investment[i] - netPlAdjust)}; })
  });

  function safeRatio(nom, denom) {
    return (denom == 0) ? 0 : nom/denom;
  }

  const plPercentAdjust = safeRatio(totals.value[0] + totals.profit[0] - totals.investment[0], totals.investment[0]);
  apexAssetAllocationCharts.plpercent.appendSeries({
    name: "% P/L",
    data: totals.value.map((v, i) => { return {x: data.t[i], y: (safeRatio(v + totals.profit[i] - totals.investment[i], totals.investment[i]) - plPercentAdjust) * 100}; })
  });
}
