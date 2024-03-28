"use strict";

function createQuoteHistoryChart(obj, name, data, unit) {
  const chartOpts = jQuery.extend(true, {}, apexOptions, {
    series: [{
      name: name,
      data: data.map(v => { return {x: v.timestamp, y: v.quote}; })
    }],
    yaxis: {
      title: { text: unit },
      min: (min) => min < 0 ? 0 : min * 0.8
    }
  });

  let chart = new ApexCharts(obj, chartOpts);
  chart.render();
};
