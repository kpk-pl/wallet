"use strict";

function setupDatetimePicker(defaultDate){
  $("#f-date").val(defaultDate);

  $('#f-date-group').datetimepicker({
    locale: typing.datetimeLocale,
    format: typing.datetimeFormat,
  });
};
