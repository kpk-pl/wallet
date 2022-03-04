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
  function priceSourceChanged() {
    if ($(this).valid()) {
      $.getJSON(addSettings.getPricingItem($(this).val()), function(data){
        $("#f-name").val(data.name);
        $("#f-link").val(data.url);
        $('#f-currency').val(data.unit);
        $('#f-quote-currency-prepend').text(data.unit);
        if (data.lastQuote)
          $('#f-quote').val(data.lastQuote);

        $.getJSON(addSettings.getQuoteData(data.url), function(quoteData){
          $('#f-quote').val(quoteData.quote);
          if (quoteData.ticker)
            $('#f-ticker').val(quoteData.ticker);
          if (quoteData.type)
            $('#f-type').val(quoteData.type);
        });
      });
    }
  }

  $("#f-price-source").change(priceSourceChanged);

  $("#f-link-open").click(function(){
    window.open($('#f-link').val(), '_blank', 'noopener,noreferrer');
  });
});

$(function(){
  const validationSettings = {
    submitHandler: function(){
      $.post(addSettings.submitUrl, $('.tab-pane.active > form').serialize(), function(data) {
        $(location).attr("href", addSettings.getNextUrl(data));
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
  };

  $("#form-general").validate(validationSettings);
  $("#form-cash").validate(validationSettings);
});
