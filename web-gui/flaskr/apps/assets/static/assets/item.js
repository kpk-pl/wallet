$(function(){
  for (let type of typing.operationTypes) {
    $(`.badge-op-${type}`).css('background-color', styling.operationColor(type));
  }
});

function setupChart(name, currency, data, operations) {
  let types = {};
  for (let type of typing.operationTypes)
    types[type] = { operations: [] };

  operations.forEach(op => types[op.type].operations.push(op));

  let chart = new Chart($('#chart'), {
    type: 'line',
    data: {
      datasets: [{
        label: name,
        data: data,
        parsing: { xAxisKey: 'timestamp', yAxisKey: 'quote' },
        cubicInterpolationMode: 'monotone',
        pointRadius: 0,
        fill: true,
        backgroundColor: 'rgba(0, 123, 255, 0.65)',
        borderColor: 'rgba(0, 123, 255, 1)',
        borderWidth: 2,
        order: 1
      }]
    },
    options: {
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day', displayFormats: { day: 'D MMM YY' } }
        },
        y: {
          title: { display: true, text: currency }
        },
      },
      plugins: {
        legend: {
          labels: {
            filter: function(legendItem) {
              return legendItem.datasetIndex == 0;
            }
          }
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              if (ctx.datasetIndex == 0)
                return `${ctx.dataset.label}: ${styling.asCurrency(ctx.parsed.y, currency)}`;

              const op = types[ctx.dataset.label].operations[ctx.dataIndex];
              return `${op.type} ${op.quantity} @ ${styling.asCurrency(op.price/op.quantity, currency)}`;
            }
          }
        }
      }
    }
  });

  for (let type in types) {
    chart.data.datasets.push({
      label: type,
      data: types[type].operations.map(function(op){ return {t: op.date, y: op.price/op.quantity}; }),
      parsing: { xAxisKey: 't', yAxisKey: 'y' },
      pointRadius: 4,
      showLine: false,
      pointBackgroundColor: styling.operationColor(type),
      pointBorderColor: styling.operationColor(type)
    });
  }

  chart.update();
}
