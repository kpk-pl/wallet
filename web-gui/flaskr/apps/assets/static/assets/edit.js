"use strict";

var editSettings;

function initialize(settings) {
  editSettings = settings;

  $('#f-labels').tagsinput({
    tagClass: 'badge badge-success',
    typeaheadjs: {
      source: function(query, sync){ sync(editSettings.headerLabels); }
    }
  });
}

$(function(){
  $("#f-link-open").click(function(){
    window.open($('#f-link').val(), '_blank', 'noopener,noreferrer');
  });

  const validationSettings = {
    submitHandler: function(){
      $.post(editSettings.submitUrl, $('#edit-form').serialize())
        .done(function(data) {
          $(location).attr("href", editSettings.getNextUrl(data));
        })
        .fail(function(data) {
          $(document).Toasts('create', {
            class: 'bg-danger',
            title: 'Error',
            subtitle: `Code ${data.responseJSON.code}`,
            body: data.responseJSON.message,
          });
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

  $("#edit-form").validate(validationSettings);
});
