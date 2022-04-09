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

  const netPlAdjust = totals.value[0] - totals.investment[0];
  assetAllocationCharts.netpl.data.datasets.push({
    data: totals.value.map((v, i) => v - totals.investment[i] - netPlAdjust),
    label: 'Net P/L',
    cubicInterpolationMode: 'monotone', pointRadius: 0, borderWidth: 1
  });

  const plPercentAdjust = safeRatio(totals.value[0] - totals.investment[0], totals.investment[0]);
  assetAllocationCharts.plpercent.data.datasets.push({
    data: totals.value.map((v, i) => (safeRatio(v - totals.investment[i], totals.investment[i]) - plPercentAdjust) * 100),
    label: '% P/L',
    cubicInterpolationMode: 'monotone', pointRadius: 0, borderWidth: 1
  });

  for (let [type, chart] of Object.entries(assetAllocationCharts)) {
    chart.update();
  }
}
