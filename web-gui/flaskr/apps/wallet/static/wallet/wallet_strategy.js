var strategyTable;

$(function(){
  let strategyTableElement = $('#strategyTable').DataTable({
    "paging": false,
    "lengthChange": false,
    "searching": false,
    "ordering": false,
    "order": [[1, "desc"]],
    "info": false,
    "autoWidth": false,
    "responsive": false,
    "columnDefs": [
      { "type": "string", "targets": [0] },
      { "type": "num-fmt", "className": "text-right", "targets": [1, 2, 4] },
      { "type": "num-fmt", "className": "text-right color-gain", "targets": [3] }
    ]
  });

  strategyTable = new StrategyTable(strategyTableElement, {
    name: 0, share: 1,
    netValue: {
      column: 2,
      format: x => x.toFixed(0)
    },
    deviation: {
      column: 3,
      format: x => (x > 0 ? '+' + x.toFixed(1) : x.toFixed(1))
    },
    requiredChange: {
      column: 4,
      format: x => (x > 0 ? '+' + x.toFixed(0) : x.toFixed(0))
    }
  });
});

function updateStrategyAllocation(data) {
  strategyTable.fillStrategy(data, function(assetType){
    return [assetType.name,
            String(assetType.percentage) + '%',
            null,
            null,
            null]
  })

  strategyTable.fillAllocation(data)
  strategyTable.updateDeviation(data)
  $('#strategyTable td.color-gain').each(styling.colorGain)
}
