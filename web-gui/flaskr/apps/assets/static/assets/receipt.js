"use strict";

$(function(){
  $('#f-date-group').datetimepicker({
    locale: 'pl',
    format: 'YYYY-MM-DD HH:mm:ss',
  });

  $("form").validate({
    rules: {
      date: { isDate: true },
      currencyConversion: { greaterThan: 0 },
      price: { greaterThan: 0 },
      quantity: { greaterThan: 0 },
    },
    errorElement: 'span',
    errorPlacement: function (error, element) {
            error.addClass('invalid-feedback');
            element.closest('.form-group').append(error);
    },
    highlight: function (element, errorClass, validClass) {
            $(element).addClass('is-invalid');
    },
    unhighlight: function (element, errorClass, validClass) {
            $(element).removeClass('is-invalid');
    },
  });
});
