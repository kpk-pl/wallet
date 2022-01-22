"use strict";

$(function () {
  $.fn.dataTable.Buttons.defaults.dom.collection.className += " dropdown-menu-right";
  let datatable = $('#resultsTable').DataTable({
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

  datatable.buttons().container().appendTo("#tableElements");

  $("#list-filter").on("keyup search input paste cut", function() {
    datatable.search(this.value).draw();
  });

  $('.color-gain').each(styling.colorGain);
});

function submitTimerangeForm(e) {
  e.preventDefault()

  let url = URI(window.location.href);
  url.removeSearch("timerange").addSearch("timerange", $('#f-timerange').val());
  $(location).attr("href", url.toString());
}
