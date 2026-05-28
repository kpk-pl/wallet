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
        title: { text: unit },
        min: (min) => min < 0 ? 0 : min * 0.8
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
        throw new Error("Invalid response " + response.status);
      }
      return response.json();
    } catch(e) {
      $(document).Toasts('create', {
        class: 'bg-danger',
        title: 'Error',
        body: 'CSV upload failed: ' + e.message,
      });
    }
  }

  fetchCsv(file).then(function(quotes){
    if (!quotes) return;
    ui.importNew(
      quotes.map(function(e){ return {x: Date.parse(e.timestamp), y: e.quote}; }));
  });
}

function loadOnlineQuotes() {
  const source = $('#f-source').val();
  const from = $("#f-date-from").val();
  const to = $("#f-date-to").val();
  if (!from || !to) {
    $(document).Toasts('create', {
      class: 'bg-warning',
      title: 'Missing dates',
      body: 'Please select both the "Since" and "To" dates.',
    });
    return;
  }

  async function fetchHistory() {
    const ctrl = new AbortController();
    setTimeout(() => ctrl.abort(), 15000);

    const url = settings.historyUrl
      + "?id=" + encodeURIComponent(settings.id)
      + "&source=" + encodeURIComponent(source)
      + "&from=" + encodeURIComponent(from)
      + "&to=" + encodeURIComponent(to);

    try {
      let response = await fetch(url, {signal: ctrl.signal});
      let body = await response.json();
      if (!response.ok) {
        throw new Error(body && body.error ? body.error : "Invalid response " + response.status);
      }
      return body;
    } catch(e) {
      $(document).Toasts('create', {
        class: 'bg-danger',
        title: 'Error',
        body: 'Import failed: ' + e.message,
      });
    }
  }

  fetchHistory().then(function(quotes){
    if (!quotes) return;
    ui.importNew(
      quotes.map(function(e){ return {x: Date.parse(e.timestamp), y: e.quote}; }));
  });
}

function toggleSource() {
  const source = $('#f-source').val();
  $('#source-csv').toggle(source === 'csv');
  $('#source-online').toggle(source !== 'csv');
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

  if ($('#f-date-to').length) {
    $('#f-date-to-group').datetimepicker('date', moment());
    $('#f-date-from-group').datetimepicker('date', moment().subtract(30, 'days'));
  }

  toggleSource();

  $('#f-method').change(function(){ ui.update(); });
  $('#f-source-file').change(function(){ ui.reset(); });
  $('#f-source').change(function(){ toggleSource(); ui.reset(); });
});
