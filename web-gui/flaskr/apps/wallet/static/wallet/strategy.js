"use strict";

var settings;
function initialize(s) {
  settings = s;
}

$(function () {
  $.fn.dataTable.Buttons.defaults.dom.collection.className += " dropdown-menu-right";

  function makeAdjustmentInput(step, cls) {
    return '<input type="number" step="' + step.toString() + '" class="' + cls + ' form-control form-control-sm"></input>';
  }

  let assetAdjustmentTableElement = $('#assetAdjustmentTable').DataTable({
    paging: false,
    searching: false,
    ordering: true,
    order: [[2, "asc"]],
    info: false,
    autoWidth: false,
    responsive: true,
    columns: [
      {"data": function(row){
        return '<a href="' + settings.assetUri.replace('ASSET_ID', row.id) + '">' + row.name + "</a>";
      }},
      {"data": "institution"},
      {"data": "category"},
      {"data": "quantity"},
      {"data": function(row){
        return parseFloat(row.unitPrice).toFixed(2) + " " + row.currency;
      }},
      {"defaultContent": makeAdjustmentInput(1, "assetAdjustmentTableAdjustmentInput")},
      {"defaultContent": "0"}
    ],
    columnDefs: [
      { type: "string", targets: [0, 1, 2] },
      { type: "num-fmt", className: "text-right", targets: [3, 4] },
      { type: "num-fmt", className: "text-right color-gain", targets: [6] },
      { orderable: false, targets: [5] },
      { visible: false, targets: [] },
    ],
  });

  let assetAdjustmentTable = new StrategyAssetAdjustmentTable(assetAdjustmentTableElement, {
    adjustment: 5,
    adjustedValue: {column: 6, format: x => x.toFixed(2)},
  });

  let strategyTableElement = $('#strategyTable').DataTable({
    paging: false,
    searching: false,
    ordering: true,
    order: [[1, "desc"]],
    info: false,
    autoWidth: false,
    responsive: true,
    buttons: [
      { extend: "colvis", className: "btn-sm py-0" },
    ],
    columnDefs: [
      { type: "readonly", targets: [3, 4, 5, 6, 7] },
      { type: "string", targets: [0, 2] },
      { type: "num-fmt", className: "text-right", targets: [1, 3] },
      { type: "num-fmt", className: "text-right color-gain", targets: [5, 6, 7] },
      { orderable: false, targets: [2, 4] },
      { visible: false, targets: [2] },
    ],
    footerCallback: footerCallback
  });
  strategyTableElement.buttons().container().appendTo("#tableElements");

  let strategyTable = new StrategyTable(strategyTableElement, assetAdjustmentTable, {
    name: 0,
    share: 1,
    netAdjust: 4,
    netValue: {column: 3, format: x => x.toFixed(2)},
    deviation: {column: 5, format: x => (x > 0 ? '+'+x.toFixed(1) : x.toFixed(1))},
    requiredChange: {column: 6, format: x => x.toFixed(2)},
    rebalancingChange: {column: 7, format: x => x.toFixed(2)}
  });

  $.getJSON(settings.strategyUri)
    .done(function(data) { updateStrategyAllocation(data); })
    .fail(function(data){
      $(document).Toasts('create', {
        class: 'bg-warning',
        title: 'Warning',
        body: data.responseJSON.message,
      });

      $.getJSON(settings.strategyUriFallback)
        .done(function(data){ updateStrategyAllocation(data, true); })
        .fail(function(data){
          $(document).Toasts('create', {
            class: 'bg-critical',
            title: 'Error',
            body: data.responseJSON.message,
          });
        });
    });

  function footerCallback(row, data, start, end, display) {
    let api = this.api();

    function intVal(i) {
      if (typeof i === 'string')
        return parseFloat(i);
      return typeof i === 'number' ? i : 0;
    };

    for (let column of [3,6,7]) {
      const total = api.column(column).data().reduce((a,b) => intVal(a) + intVal(b), 0);
      $(api.column(column).footer()).html(styling.asCurrencyNumber(total, settings.currency));
    }

    function adjVal(i) {
      if (typeof i === 'object') {
        let inputElement = i.getElementsByTagName('input')[0];
        return inputElement !== undefined ? Number(inputElement.value) : 0;
      }
      return i;
    }
    const adjTotal = api.column(4).nodes().reduce((a, b) => adjVal(a) + adjVal(b), 0);
    $(api.column(4).footer()).html(styling.asCurrencyNumber(adjTotal, settings.currency));
  }

  function updateStrategyAllocation(data, simplified=false) {
    function makeList(array, tag='ul', classes=[]) {
      let result = `<${tag} class="${classes.join(' ')}">`;
      for (let element of array) {
        result += `<li>${element}</li>`;
      }
      result += `</${tag}>`;
      return result;
    }

    strategyTable.fillStrategy(data, function(assetType){
      let constituents = []
      for (let category of assetType.categories)
      {
        constituents.push(typeof category == "string" ? category : `${category.name} [${category.percentage}%]`)
      }

      return [assetType.name,
              String(assetType.percentage) + '%',
              makeList(constituents, 'ul', ['list-unstyled', 'm-0']),
              null,
              simplified ? null : makeAdjustmentInput(100, 'strategyTableDeviationInput'),
              null,
              null,
              null]
    });

    assetAdjustmentTable.fillAssets(data);
    strategyTable.fillAllocation(data);

    function updateStrategyTable(){
      strategyTable.updateDeviation(data);
      $('#strategyTable td.color-gain').each(styling.colorGain)
    }

    function updateAssetAdjustmentTable(){
      assetAdjustmentTable.updateAdjustedValues();
      $('#assetAdjustmentTable td.color-gain').each(styling.colorGain)
    }

    updateStrategyTable();
    updateAssetAdjustmentTable();

    $(".strategyTableDeviationInput").change(updateStrategyTable);
    $(".assetAdjustmentTableAdjustmentInput").change(function(){
      updateAssetAdjustmentTable();
      updateStrategyTable();
    });
  }
});
