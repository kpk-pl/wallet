class CategoryChart {
  constructor(allocation) {
    this.allocation = allocation
    this.categories = Object.keys(this.allocation)
    this.subcategories = this.categories.map(c => { return Object.keys(this.allocation[c]).map(s => c + (s != 'null' ? (' ' + s) : '')); }).flat()
  }

  makeChart(node) {
    let allocation = this.allocation
    let categories = this.categories
    let subcategories = this.subcategories

    return new Chart(node.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: categories.concat(this.subcategories),
        datasets: [{
          data: categories.map(function(c){ return Object.values(allocation[c]).reduce((a,b) => a+b); }),
          borderWidth: 1
        }, {
          data: categories.map(function(c) { return Object.values(allocation[c]); }).flat(),
          borderWidth: 1
        }]
      },
      options: {
        maintainAspectRatio: false,
        responsive: true,
        cutoutPercentage: 30,
        plugins: {
          colorschemes: {
            scheme: 'tableau.Classic10'
          },
          labels: {
            render: 'percentage',
            fontColor: 'black',
            fontSize: 16,
            precision: 1
          }
        },
        tooltips: {
          callbacks: {
            label: function(tooltipItem, data) {
              var dataset = data.datasets[tooltipItem.datasetIndex];
              var total = dataset.data.reduce(function(previousValue, currentValue, currentIndex, array) {
                        return previousValue + currentValue;
                      });
              var currentValue = dataset.data[tooltipItem.index];
              var percentage = Number((currentValue/total*100).toFixed(1));
              var labelIdx = tooltipItem.datasetIndex == 0 ? tooltipItem.index : categories.length + tooltipItem.index;
              return data.labels[labelIdx] + ': ' + Number(currentValue.toFixed(2)) + ' PLN [' + percentage + "%]";
            }
          }
        },
        legend: {
          labels: {
            generateLabels: function(chart) {
              // Get the default label list
              const original = Chart.defaults.doughnut.legend.labels.generateLabels;
              const labelsOriginal = original.call(this, chart);

              // Build an array of colors used in the datasets of the chart
              var datasetColors = chart.data.datasets.map(e => e.backgroundColor).flat();

              function findSubIndexes(category) {
                var counter = 0
                for (var c = 0; c < category; ++c) {
                  counter += Object.keys(allocation[categories[c]]).length
                }
                return Array.from({length: Object.keys(allocation[categories[category]]).length})
                  .map((_, i) => i + counter);
              };

              // Modify the color and hide state of each label
              labelsOriginal.forEach(label => {
                  label.datasetIndex = label.index < categories.length ? 0 : 1;

                  // The hidden state must match the dataset's hidden state
                  label.hidden = !chart.isDatasetVisible(label.datasetIndex);

                  // Change the color to match the dataset
                  label.fillStyle = datasetColors[label.index];

                  // Embed information about category mappings
                  if (label.index < categories.length) {
                    label.subcategories = findSubIndexes(label.index);
                  }
              });

              return labelsOriginal;
            }
          },
          onClick: function(mouseEvent, legendItem) {
            var ctx = this.chart;
            var categoryMeta = ctx.getDatasetMeta(0);
            var subcategoryMeta = ctx.getDatasetMeta(1);

            if (legendItem.index < categories.length) {
              var hidden = categoryMeta.data[legendItem.index].hidden
              // hide category
              categoryMeta.data[legendItem.index].hidden = !hidden
              // and all it's subcategories
              legendItem.subcategories.forEach(function(idx){
                subcategoryMeta.data[idx].hidden = !hidden;
              });
            }
            else {
              var subIndex = legendItem.index - categories.length
              var hidden = subcategoryMeta.data[subIndex].hidden
              // hide subcategory
              subcategoryMeta.data[subIndex].hidden = !hidden;

              // and whole dataset above
              if (!hidden) {
                categoryMeta.data.forEach(function(e){e.hidden = true;});
              } else {
                var hiddenSubs = subcategoryMeta.data.reduce((p, d) => p + (d.hidden ? 1 : 0), 0)
                if (hiddenSubs == 0)
                  categoryMeta.data.forEach(function(e){e.hidden = false;});
              }
            }

            this.chart.update();
          }
        }
      }
    });
  }
}
