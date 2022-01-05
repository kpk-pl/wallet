"use strict";

var addSettings;

function initialize(settings) {
  addSettings = settings;

  ['#f-labels', '#c-labels'].forEach(function(selector){
    $(selector).tagsinput({
      tagClass: 'badge badge-success',
      typeaheadjs: {
        source: function(query, sync){ sync(addSettings.headerLabels); }
      }
    });
  });
}

$(function(){
  function linkChange() {
    function setDefault(selector, value) {
      let element = $(selector)
      if ((element.val() === null || element.val() === "") && value !== null)
        element.val(value).change()
    }

    if ($(this).valid()) {
      $.getJSON(addSettings.getQuoteUrl(), function(quote){
        setDefault('#f-name', quote['name'])
        setDefault('#f-type', quote['type'])
        setDefault('#f-currency', quote['currency'])
        setDefault('#f-ticker', quote['ticker'])
        setDefault('#f-quote', quote['quote'])
      })
    }
  }

  $("#f-link").change(linkChange);
  $("#f-link-get").click(linkChange);

  $("#f-currency").change(function() {
    $('#f-quote-currency-prepend').text($(this).val());
  });

  function priceUnitMatch(lhs, rhs) {
    if (lhs == rhs) return true;
    if (lhs == "GBP" && rhs == "GBX") return true;
    if (lhs == "GBX" && rhs == "GBP") return true;
    return false;
  }

  $("#f-currency").change(function() {
    let currency = $(this).val()
    $("#f-price-source > option").each(function() {
      $(this).prop('disabled', !priceUnitMatch($(this).attr('data-price-source-unit'), currency))
    })
  })
});

$(function(){
  $("form").validate({
    submitHandler: function(){
      $.post(addSettings.submitUrl, $('.tab-pane.active > form').serialize(), function(data) {
        $(location).attr("href", addSettings.nextUrl);
      });
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
});
