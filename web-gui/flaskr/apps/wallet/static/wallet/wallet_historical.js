var assetAllocationCharts = Object.create(null);

$(function(){
  for (let type of ['netpl', 'plpercent', 'summary', 'value', 'investment', 'share']) {
    assetAllocationCharts[type] = new Chart(document.getElementById('assetAllocation_chart_' + type).getContext('2d'), {
      type: 'line',
      data: { labels: [], datasets: [] },
      options: {
        maintainAspectRatio: false,
        responsive: true,
        plugins: {
          colorschemes: {
            scheme: ((type == 'netpl' || type == 'plpercent' || type == 'summary') ? 'office.Frame6' : 'tableau.MillerStone11'),
            fillAlpha: (type == 'summary' ? 0.8 : 1)
          }
        },
        hover: { mode: 'nearest' },
        tooltips: { enabled: true, },
        scales: {
          xAxes: [{
            type: 'time',
            time: { unit: 'day', displayFormats: { day: 'D MMM YY' } }
          }],
          yAxes: [{
            stacked: (type != 'summary'),
            scaleLabel: { display: true, labelString: (['plpercent', 'share'].includes(type) ? '%' : 'PLN') }
          }]
        }
      }
    });
  }
});

function updateAllocationCharts(data){
  for (let [type, chart] of Object.entries(assetAllocationCharts)) {
    chart.data.labels = data.t
  }

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
    assetAllocationCharts.value.data.datasets.push({
      data: mapping[category].value,
      label: category,
      cubicInterpolationMode: 'monotone', pointRadius: 0, borderWidth: 1
    });
    assetAllocationCharts.investment.data.datasets.push({
      data: mapping[category].investment,
      label: category,
      cubicInterpolationMode: 'monotone', pointRadius: 0, borderWidth: 1
    });
    assetAllocationCharts.share.data.datasets.push({
      data: mapping[category].value.map((v, i) => v/totals.value[i]*100),
      label: category,
      cubicInterpolationMode: 'monotone', pointRadius: 0, borderWidth: 1
    });
  }

  function safeRatio(nom, denom) {
    if (denom == 0)
      return 0;
    return nom/denom;
  }

  assetAllocationCharts.summary.data.datasets.push({
    data: totals.value,
    label: 'Value',
    cubicInterpolationMode: 'monotone', pointRadius: 0, borderWidth: 1
  });
  assetAllocationCharts.summary.data.datasets.push({
    data: totals.investment,
    label: 'Investment',
    cubicInterpolationMode: 'monotone', pointRadius: 0, borderWidth: 1
  });

  const netPlAdjust = totals.value[0] + totals.profit[0] - totals.investment[0];
  assetAllocationCharts.netpl.data.datasets.push({
    data: totals.value.map((v, i) => v + totals.profit[i] - totals.investment[i] - netPlAdjust),
    label: 'Net P/L',
    cubicInterpolationMode: 'monotone', pointRadius: 0, borderWidth: 1
  });

  const plPercentAdjust = safeRatio(totals.value[0] + totals.profit[0] - totals.investment[0], totals.investment[0]);
  assetAllocationCharts.plpercent.data.datasets.push({
    data: totals.value.map((v, i) => (safeRatio(v + totals.profit[i] - totals.investment[i], totals.investment[i]) - plPercentAdjust) * 100),
    label: '% P/L',
    cubicInterpolationMode: 'monotone', pointRadius: 0, borderWidth: 1
  });

  for (let [type, chart] of Object.entries(assetAllocationCharts)) {
    chart.update();
  }
}
