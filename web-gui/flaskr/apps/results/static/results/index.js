"use strict";

$(function () {
  let datatable = $('#resultsTable').DataTable({
    paging: false,
    lengthChange: false,
    searching: true,
    ordering: true,
    order: [[5, "desc"]],
    info: false,
    autoWidth: false,
    responsive: true,
    buttons: [{
      extend: "colvis", align: "button-right", className: "btn-sm py-0"
    }],
    columnDefs: [
      { visible: false, targets: [2, 3] }
    ],
  });

  datatable.buttons().container().appendTo("#tableElements");

  $("#list-filter").on("keyup search input paste cut", function() {
    datatable.search(this.value).draw();
  });
});
