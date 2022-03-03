"use strict";

$(function(){
  for (let type of typing.operationTypes) {
    $(`.badge-op-${type}`).css('background-color', styling.operationColor(type));
  }
});

$(function () {
  $.fn.dataTable.Buttons.defaults.dom.collection.className += " dropdown-menu-right";
  let resultsDatatable = $('#resultsTable').DataTable({
    paging: false,
    searching: true,
    ordering: true,
    order: [[6, "desc"]],
    info: false,
    autoWidth: false,
    responsive: true,
    buttons: [{
      extend: "colvis", className: "btn-sm py-0"
    }],
    columnDefs: [
      { visible: false, targets: [3, 4] }
    ],
  });

  let breakdownDatatable = $('#breakdownTable').DataTable({
    paging: false,
    searching: true,
    ordering: true,
    order: [[0, "asc"]],
    info: false,
    autoWidth: false,
    responsive: true,
    buttons: [{
      extend: "colvis", className: "btn-sm py-0"
    }],
    columnDefs: [
      { type: "string", targets: [0, 1, 2, 3] },
      { type: "num-fmt", targets: [4, 5, 6, 7, 8, 9] },
      { visible: false, targets: [0] }
    ],
  });

  resultsDatatable.buttons().container().appendTo("#resultsTableElements");
  breakdownDatatable.buttons().container().appendTo("#breakdownTableElements");

  $("#resultsTableFilter").on("keyup search input paste cut", function() {
    resultsDatatable.search(this.value).draw();
  });
  $("#breakdownTableFilter").on("keyup search input paste cut", function() {
    breakdownDatatable.search(this.value).draw();
  });

  $('.color-gain').each(styling.colorGain);
});

function submitTimerangeForm(e) {
  e.preventDefault()

  let url = URI(window.location.href);
  url.removeSearch("timerange").addSearch("timerange", $('#f-timerange').val());
  $(location).attr("href", url.toString());
}
