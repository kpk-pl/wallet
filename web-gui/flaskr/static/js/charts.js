const apexOptions = function(){
    const pallete = ['#008FFB', '#FEB019', '#4CAF50', '#FF4560', '#775DD0', '#00E396', '#F9CE1D', '#F9A3A4', '#69D2E7', '#C7F464', '#A300D6', '#5A2A27'];

    return {
      chart: {
        type: 'area',
        height: '100%',
        stacked: false
      },
      series: [],
      annotations: {
        yaxis: []
      },
      legend: { position: 'top' },
      dataLabels: { enabled: false },
      stroke: { width: 3 },
      xaxis: {
        type: 'datetime',
        datetimeUTC: false,
        tickAmount: 40,
        labels: {
          formatter: function(val, timestamp) {
            return moment(timestamp).format("D MMM YY");
          }
        }
      },
      yaxis: {
        type: 'number',
        tickAmount: 20,
        decimalsInFloat: 2,
        tooltip: { enabled: true }
      },
      colors: pallete,
      fill: {
        colors: pallete,
        type: 'solid',
        opacity: 0.6
      },
      markers: {
        colors: pallete,
        strokeWidth: 1
      }
    };
}();
