"use strict";

var settings;
var ui;

class ChartUi {
  constructor(chartSettings) {
    this.existingQuotes = chartSettings.existingQuotes;
    this.importedQuotes = [];
    this.init(chartSettings.name, chartSettings.unit);
  }

  init(name, unit) {
    this.chart = new Chart($('#chart'), {
      type: 'line',
      data: {
        datasets: [{
          label: name,
          cubicInterpolationMode: 'monotone',
          pointRadius: 2,
          data: this.existingQuotes,
          parsing: { xAxisKey: 'timestamp', yAxisKey: 'quote' },
          backgroundColor: 'rgba(0, 123, 255, 0.65)',
          borderColor: 'rgba(0, 123, 255, 1)',
          borderWidth: 2,
          fill: true,
          order: 2
        }, {
          label: 'Imported data',
          cubicInterpolationMode: 'monotone',
          pointRadius: 2,
          data: [],
          parsing: { xAxisKey: 'timestamp', yAxisKey: 'quote' },
          fill: false,
          borderColor: 'rgba(255, 123, 0, 1)',
          borderWidth: 2,
          order: 1
        }]
      },
      options: {
        animation: { duration: 0 },
        scales: {
          x: {
            type: 'time',
            time: { unit: 'day', displayFormats: { day: 'D MMM YY' } }
          },
          y: {
            title: { display: true, text: unit }
          },
        }
      }
    });
  }

  importNew(quotes) {
    this.importedQuotes = quotes;
    this.update();
  }

  update() {
    let method = $('#f-method').val();
    let filteredQuotes = this.existingQuotes;
    if (method == 'replace' && this.importedQuotes.length > 0) {
      filteredQuotes = filteredQuotes.filter(function(q) {
        return q.timestamp < this.importedQuotes.at(0).timestamp || q.timestamp > this.importedQuotes.at(-1).timestamp;
      });
    }

    let combinedData = filteredQuotes.concat(this.importedQuotes).sort((lhs, rhs) => { return lhs.timestamp - rhs.timestamp; });

    this.chart.data.datasets[0].data = combinedData;
    this.chart.data.datasets[1].data = this.importedQuotes;
    this.chart.update();

    $("#f-submit").attr('disabled', this.importedQuotes.length == 0);
  }

  reset() {
    this.importedQuotes = [];
    this.update();
  }
};

function init(pageSettings) {
  settings = pageSettings;
  ui = new ChartUi(pageSettings.chart);
}

function loadCsvQuotes() {
  const file = $("#f-source-file")[0].files[0];

  async function fetchCsv(file) {
    let formData = new FormData();
    formData.append("file", file);

    const ctrl = new AbortController()
    setTimeout(() => ctrl.abort(), 5000);

    try {
      let response = await fetch(settings.csvUploadUrl, {method: "POST", body: formData, signal: ctrl.signal});
      if (!response.ok) {
        throw new Error("Invalid response " + r.status());
      }
      return response.json();
    } catch(e) {
      // TODO: maybe display a popup with the error
    }
  }

  fetchCsv(file).then(function(quotes){
    ui.importNew(
      quotes.map(function(e){ return {timestamp: Date.parse(e.timestamp), quote: e.quote}; }));
  });
}

function submitImport(event) {
  event.preventDefault();

  let payload = {
    id: settings.id,
    method: $('#f-method').val(),
    data: JSON.stringify(ui.importedQuotes)
  };

  $.post(settings.submitUrl, payload, function(data) {
    $(location).attr("href", settings.nextUrl);
  })
}

$(function(){
  $('.f-date-group').datetimepicker({
    locale: 'pl',
    format: 'YYYY-MM-DD',
  });
  bsCustomFileInput.init();

  $('#f-method').change(function(){ ui.update(); });
  $('#f-source-file').change(function(){ ui.reset(); });
  $('#f-source').change(function(){ ui.reset(); });
});
