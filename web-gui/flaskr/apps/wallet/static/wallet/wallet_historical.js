var assetAllocationCharts = Object.create(null);

$(function(){
  for (let type of ['netpl', 'value', 'investment', 'share']) {
    assetAllocationCharts[type] = new Chart(document.getElementById('assetAllocation_chart_' + type).getContext('2d'), {
      type: 'line',
      data: { labels: [], datasets: [] },
      options: {
        maintainAspectRatio: false,
        responsive: true,
        plugins: {
          colorschemes: { scheme: (type == 'netpl' ? 'tableau.ColorBlind10' : 'tableau.MillerStone11'), fillAlpha: 1 }
        },
        hover: { mode: 'nearest' },
        tooltips: {
          enabled: true,
        },
        scales: {
          xAxes: [{
            type: 'time',
            time: { unit: 'day', displayFormats: { day: 'D MMM YY' } }
          }],
          yAxes: [{
            stacked: true,
            scaleLabel: { display: true, labelString: (['netpl', 'share'].includes(type) ? '%' : 'PLN') }
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
      return asset.category + ' ' + asset.subcategory;
    return asset.category;
  }

  let mapping = Object.create(null);
  let totals = {'value': new Array(data.t.length).fill(0), 'investment': new Array(data.t.length).fill(0)}
  for (let asset of data.assets) {
    const cat = category(asset);
    if (cat in mapping) {
      mapping[cat].value = mapping[cat].value.map((v, i) => v + asset.value[i]);
      mapping[cat].investment = mapping[cat].investment.map((v, i) => v + asset.investedValue[i]);
    } else {
      mapping[cat] = {'value': asset.value, 'investment': asset.investedValue};
    }

    totals.value = totals.value.map((v, i) => v + asset.value[i]);
    totals.investment = totals.investment.map((v, i) => v + asset.investedValue[i]);
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

  const netplAdjust = safeRatio(totals.value[0] - totals.investment[0], totals.investment[0]);
  assetAllocationCharts.netpl.data.datasets.push({
    data: totals.value.map((v, i) => (safeRatio(v - totals.investment[i], totals.investment[i]) - netplAdjust) * 100),
    label: 'Net P/L',
    cubicInterpolationMode: 'monotone', pointRadius: 0, borderWidth: 1
  });

  for (let [type, chart] of Object.entries(assetAllocationCharts)) {
    chart.update();
  }
}
