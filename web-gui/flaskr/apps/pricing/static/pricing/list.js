"use strict";

$(function () {
  let datatable = $('#pricingTable').DataTable({
    "paging": false,
    "lengthChange": false,
    "searching": true,
    "ordering": true,
    "info": false,
    "autoWidth": false,
    "responsive": true,
  });

  $("#list-filter").on("keyup search input paste cut", function() {
    datatable.search(this.value).draw();
  });
});
