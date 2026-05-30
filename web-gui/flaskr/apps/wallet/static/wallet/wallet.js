var strategyTable;

$('.color-gain').each(styling.colorGain);

$(function(){
  $.fn.dataTable.Buttons.defaults.dom.collection.className += " dropdown-menu-right";
  let datatable = $('#openAssets').DataTable({
    paging: false,
    searching: true,
    ordering: true,
    order: [[8, "desc"]],
    info: false,
    autoWidth: false,
    responsive: true,
    buttons: [{
      extend: "colvis", className: "btn-sm py-0"
    }],
    columnDefs: [
      { type: "string", targets: [0, 1, 2, 3] },
      { type: "num-fmt", targets: [4, 5, 6, 7, 8, 9, 10, 11] },
      { orderable: false, targets: [] },
      { visible: false, targets: [1, 3, 4, 6, 8, 11] },
    ],
  });

  datatable.buttons().container().appendTo("#tableElements");

  if (categoryAllocation) {
    let categoryChart = new CategoryChart(categoryAllocation, defaultCurrency).makeChart(document.getElementById('allocationChart'));
  }

  $("#wallet-filter").on("keyup search input paste cut", function() {
    datatable.search(this.value).draw();
  });
});

function historicalValueDone(data) {
  updateSparklines(data, 3, asset => $('#sparkline-' + asset.id));
  updateAggregatedSparklines(data, 3);
  updateAllocationCharts(data);
}

function updateAggregatedSparklines(historicalData, months) {
  const n = historicalData.t.length;
  for (const [aggKey, ids] of Object.entries(aggregatedSparklinesMap)) {
    const group = historicalData.assets.filter(a => ids.includes(a.id));
    if (group.length === 0) continue;
    const summed = {
      value: Array.from({length: n}, (_, i) => group.reduce((s, a) => s + parseFloat(a.value[i] || 0), 0)),
      profit: Array.from({length: n}, (_, i) => group.reduce((s, a) => s + parseFloat(a.profit[i] || 0), 0)),
      investedValue: Array.from({length: n}, (_, i) => group.reduce((s, a) => s + parseFloat(a.investedValue[i] || 0), 0)),
    };
    updateSparklines({t: historicalData.t, assets: [summed]}, months, () => $('#sparkline-' + aggKey));
  }
}
