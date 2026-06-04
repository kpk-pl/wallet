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
    responsive: false,
    scrollX: true,
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

  // With scrollX the header is a cloned table whose column widths don't follow
  // the body when the viewport reflows. Switching between portrait and
  // landscape on mobile changes the available width but doesn't reliably
  // trigger DataTables' own resize adjustment, leaving the header misaligned.
  // Re-measure once the new orientation has settled.
  $(window).on('orientationchange', function () {
    setTimeout(function () {
      datatable.columns.adjust();
    }, 200);
  });

  if (categoryAllocation) {
    let categoryChart = new CategoryChart(categoryAllocation, defaultCurrency).makeChart(document.getElementById('allocationChart'));
  }

  $("#wallet-filter").on("keyup search input paste cut", function() {
    datatable.search(this.value).draw();
  });

  $("#allocationRange button").on("click", function() {
    const $btn = $(this);
    if ($btn.hasClass("active")) return;
    $("#allocationRange button").removeClass("active");
    $btn.addClass("active");
    loadAllocationRange($btn.data("days"));
  });
});

function loadAllocationRange(daysBack) {
  $("#allocationRange button").prop("disabled", true);
  $("#allocationOverlay").css("display", "flex");
  $.getJSON(historicalValueUrl(daysBack))
    .done(updateAllocationCharts)
    .always(function() {
      $("#allocationOverlay").hide();
      $("#allocationRange button").prop("disabled", false);
    });
}

function historicalValueDone(data) {
  updateSparklines(data, 3, asset => $('#sparkline-' + asset.id));
  updateAggregatedSparklines(data, 3);
  updateAllocationCharts(data);

  // Sparklines are injected asynchronously and widen the change column, so the
  // scrollX header (a cloned table) drifts out of sync with the body. Recompute
  // the column widths once the cells have their final content.
  $('#openAssets').DataTable().columns.adjust();
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
