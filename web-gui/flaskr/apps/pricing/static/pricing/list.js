"use strict";

$(function () {
  let datatable = $('#pricingTable').DataTable({
    "paging": false,
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

$(function () {
  $('.refresh-quote-link').click(function(){
    $.ajax({
      url: $(this).data('refresh-quote-url'),
      type: 'put'
    })
    .done(function() {
      location.reload(true);
    })
    .fail(function() {
      $(document).Toasts('create', {
        class: 'bg-warning',
        title: 'Warning',
        body: 'Could not update the quote due to internal server error',
      });
    });
  });

  $('#refresh-all-quotes').click(function(){
    $.ajax({
      url: $(this).data('refresh-all-url'),
      type: 'put'
    })
    .done(function() {
      location.reload(true);
    })
    .fail(function() {
      $(document).Toasts('create', {
        class: 'bg-warning',
        title: 'Warning',
        body: 'Could not update quotes due to internal server error',
      });
    });
  });
});
