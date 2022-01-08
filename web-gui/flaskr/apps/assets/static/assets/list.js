"use strict";

$(function () {
  $.fn.dataTable.Buttons.defaults.dom.collection.className += " dropdown-menu-right";
  let datatable = $('#assetsTable').DataTable({
    paging: false,
    searching: true,
    ordering: true,
    info: false,
    autoWidth: false,
    responsive: true,
    buttons: [{
      extend: "colvis", className: "btn-sm py-0"
    }],
    columnDefs: [
      { visible: false, targets: [1, 6] },
      { orderable: false, targets: [1] }
    ]
  });

  datatable.buttons().container().appendTo("#tableElements");

  $("#asset-filter").on("keyup search input paste cut", function() {
    datatable.search(this.value).draw();
  });
});
