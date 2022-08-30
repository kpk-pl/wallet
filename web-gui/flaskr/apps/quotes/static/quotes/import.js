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
    const chartOpts = jQuery.extend(true, {}, apexOptions, {
      series: [{
        name: name,
        data: this.existingQuotes
      },{
        name: 'Imported data',
        data: []
      }],
      yaxis: {
        title: { text: unit }
      },
      markers: { size: 3 }
    });

    this.chart = new ApexCharts(document.getElementById('chart'), chartOpts);
    this.chart.render();
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
        return q.x < this.importedQuotes.at(0).x || q.x > this.importedQuotes.at(-1).x;
      });
    }

    const combinedData = filteredQuotes.concat(this.importedQuotes).sort((lhs, rhs) => { return lhs.x - rhs.x; });
    this.chart.updateSeries([{data: combinedData}, {data: this.importedQuotes}]);

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
      quotes.map(function(e){ return {x: Date.parse(e.timestamp), y: e.quote}; }));
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
