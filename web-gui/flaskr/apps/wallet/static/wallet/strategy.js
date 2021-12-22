var strategyTable;
var strategyData;

$(function () {
  let strategyTableElement = $('#strategyTable').DataTable({
    "paging": false,
    "lengthChange": false,
    "searching": false,
    "ordering": true,
    "order": [[1, "desc"]],
    "info": false,
    "autoWidth": false,
    "responsive": true,
    "buttons": [ "colvis" ],
    "columnDefs": [
      { "type": "string", "targets": [0, 2] },
      { "type": "num-fmt", "className": "text-right", "targets": [1, 3, 5, 6] },
      { "orderable": false, "targets": [2, 4] },
      { "visible": false, "targets": [2] },
    ],
  });
  strategyTableElement.buttons().container().appendTo("#strategyTable_wrapper .col-md-6:eq(0)");

  strategyTable = new StrategyTable(strategyTableElement, {
    name: 0,
    share: 1,
    netAdjust: 4,
    netValue: {column: 3, format: x => x.toFixed(2)},
    deviation: {column: 5, format: x => (x > 0 ? '+'+x.toFixed(1) : x.toFixed(1))},
    requiredChange: {column: 6, format: x => x.toFixed(2)}
  });
});

function updateStrategyAllocation(data) {
  strategyData = data

  function makeList(array, tag='ul', classes=[]) {
    let result = `<${tag} class="${classes.join(' ')}">`
    for (let element of array) {
      result += `<li>${element}</li>`
    }
    result += `</${tag}>`
    return result
  }

  function makeAdjustmentInput() {
    return '<input type="number" class="strategyTableDeviationInput form-control form-control-sm"></input>'
  }

  strategyTable.fillStrategy(data, function(assetType){
    constituents = []
    for (let category of assetType.categories)
      constituents.push(typeof category == "string" ? category : `${category.name} [${category.percentage}%]`)

    return [assetType.name,
            String(assetType.percentage) + '%',
            makeList(constituents, 'ul', ['list-unstyled', 'm-0']),
            null,
            makeAdjustmentInput(),
            null,
            null]
  })

  strategyTable.fillAllocation(data)
  strategyTable.updateDeviation(data)

  $(".strategyTableDeviationInput").change(()=>strategyTable.updateDeviation(data));
}
