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
      { type: "num-fmt", targets: [4, 5, 6, 7, 8, 9] },
      { orderable: false, targets: [] },
      { visible: false, targets: [3, 4] },
    ],
  });

  datatable.buttons().container().appendTo("#tableElements");

  let categoryChart = new CategoryChart(categoryAllocation).makeChart(document.getElementById('allocationChart'));

  $("#wallet-filter").on("keyup search input paste cut", function() {
    datatable.search(this.value).draw();
  });
});

function historicalValueDone(data) {
  updateSparklines(data, 3, asset => $('#sparkline-' + asset.id));
  updateAllocationCharts(data);
}
