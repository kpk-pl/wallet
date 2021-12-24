var strategyTable;

$(function(){
  $('.color-gain').each(styling.colorGain);

  $('#openAssets').DataTable({
    "paging": false,
    "lengthChange": false,
    "searching": true,
    "ordering": true,
    "order": [[8, "desc"]],
    "info": false,
    "autoWidth": false,
    "responsive": true,
    "buttons": [ "colvis" ],
    "columnDefs": [
      { "type": "string", "targets": [0, 1, 2, 3] },
      { "type": "num-fmt", "targets": [4, 5, 6, 7, 8, 9] },
      { "orderable": false, "targets": [] },
      { "visible": false, "targets": [3, 4] },
    ],
  }).buttons().container().appendTo("#openAssets_wrapper .col-md-6:eq(0)");

  let categoryChart = new CategoryChart(categoryAllocation).makeChart(document.getElementById('allocationChart'));
});

function historicalValueDone(data) {
  updateSparklines(data, 3, asset => $('#sparkline-' + asset.id));
  updateAllocationCharts(data);
}
