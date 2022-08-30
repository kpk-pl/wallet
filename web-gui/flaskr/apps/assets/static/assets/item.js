$(function(){
  for (let type of typing.operationTypes) {
    $(`.badge-op-${type}`).css('background-color', styling.operationColor(type));
  }
});

function setupChart(name, currency, data, operations) {
  const chartOpts = jQuery.extend(true, {}, apexOptions, {
    series: [{
      name: name,
      data: data.map(v => { return {x: v.timestamp, y: v.quote}; })
    }],
    yaxis: {
      title: { text: currency }
    },
    annotations: {
      points: operations.filter(op => op.type != 'EARNING')
                        .map(op => { return {
        x: new Date(op.date).getTime(),
        y: op.price/op.quantity,
        marker: {
          size: 4,
          fillColor: styling.operationColor(op.type),
          strokeColor: styling.operationColor(op.type),
          radius: 2
        }
      }; })
    }
  });

  let chart = new ApexCharts(document.getElementById('chart'), chartOpts);
  chart.render();
}
