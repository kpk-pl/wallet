class CategoryChart {
  constructor(allocation, currency) {
    this.currency = currency;
    this.allocation = allocation;
    this.categories = Object.keys(this.allocation);
    this.subcategories = this.categories.map(c => { return Object.keys(this.allocation[c]).map(s => (s != 'null' ? (s + ' ') : '') + c); }).flat();
  }

  makeChart(node) {
    let chartOpts = jQuery.extend(true, {}, apexOptions, {
      chart: { type: 'pie' },
      dataLabels: { enabled: true },
      fill: { opacity: 1 },
      labels: this.categories,
      dataLabels: {
        enabled: true,
        style: { fontSize: '100%', colors: ['#444'] },
        formatter: function(value, { seriesIndex, dataPointIndex, w }) {
          return w.config.labels[seriesIndex] + ": " + Number(value).toFixed(1) + "%"
        }
      },
      tooltip: { y: { formatter: v => styling.asCurrency(v, this.currency) }},
      plotOptions: { pie: { dataLabels: { minAngleToShowLabel: 0 }}},
      xaxis: { type: 'category' },
      series: this.categories.map(c => { return Object.values(this.allocation[c]).map(x => parseFloat(x)).reduce((a,b) => a+b); }),
    });

    let chart = new ApexCharts(node, chartOpts);
    chart.render();
    return chart;

        //datasets: [{
          //data: categories.map(function(c){ return Object.values(allocation[c]).map(x => parseFloat(x)).reduce((a,b) => a+b); }),
          //borderWidth: 1
        //}, {
          //data: categories.map(function(c) { return Object.values(allocation[c]).map(x => parseFloat(x)); }).flat(),
          //borderWidth: 1
        //}]
  }
}
