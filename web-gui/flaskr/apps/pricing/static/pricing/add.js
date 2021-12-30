"use strict";

var settings;

function setupForm(s) {
  settings = s;

  $("form").validate({
    submitHandler: function() {
      $.post(settings.submitUrl, $('form').serialize(), settings.submitSuccessHandler);
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
          }
  });
}

$(function(){
  function linkChange() {
    function setDefault(selector, value) {
      let element = $(selector);
      if ((element.val() === null || element.val() === "") && value !== null)
        element.val(value).change();
    }

    if ($(this).valid()) {
      $.getJSON(settings.urlForQuotes(), function(quote){
        setDefault('#f-name', quote['name']);
        setDefault('#f-unit', quote['currency']);
        setDefault('#f-ticker', quote['ticker']);
        setDefault('#f-quote', quote['quote']);
      });
    }
  }

  $("#f-url").change(linkChange);
  $("#f-url-get").click(linkChange);

  $("#f-unit").change(function() {
    $('#f-quote-unit-prepend').text($(this).val());
  });
});
