"use strict";

function setupEditForm(settings) {
  const list = document.getElementById('urls-list');

  function newRow(value) {
    const row = document.createElement('div');
    row.className = 'input-group mb-2 url-row';

    const input = document.createElement('input');
    input.type = 'url';
    input.name = 'urls';
    input.className = 'form-control';
    input.setAttribute('data-lpignore', 'true');
    input.required = true;
    input.value = value || '';

    const buttons = document.createElement('span');
    buttons.className = 'input-group-append';
    buttons.innerHTML =
      '<button type="button" class="btn btn-outline-secondary btn-url-up" title="Move up"><i class="fas fa-arrow-up"></i></button>' +
      '<button type="button" class="btn btn-outline-secondary btn-url-down" title="Move down"><i class="fas fa-arrow-down"></i></button>' +
      '<button type="button" class="btn btn-outline-danger btn-url-remove" title="Remove"><i class="fas fa-times"></i></button>';

    row.appendChild(input);
    row.appendChild(buttons);
    return row;
  }

  $('#btn-url-add').on('click', function() {
    list.appendChild(newRow(''));
  });

  // Delegated handlers for the per-row reorder / remove buttons.
  $(list).on('click', '.btn-url-remove', function() {
    $(this).closest('.url-row').remove();
  });

  $(list).on('click', '.btn-url-up', function() {
    const row = $(this).closest('.url-row');
    const prev = row.prev('.url-row');
    if (prev.length) row.insertBefore(prev);
  });

  $(list).on('click', '.btn-url-down', function() {
    const row = $(this).closest('.url-row');
    const next = row.next('.url-row');
    if (next.length) row.insertAfter(next);
  });

  $('#edit-form').on('submit', function(event) {
    event.preventDefault();

    const urlInputs = list.querySelectorAll('input[name="urls"]');
    if (urlInputs.length === 0) {
      $(document).Toasts('create', {
        class: 'bg-danger',
        title: 'Error',
        body: 'At least one link is required',
      });
      return;
    }

    // Let the browser flag empty / malformed URLs and the required name/unit.
    if (!this.checkValidity()) {
      this.reportValidity();
      return;
    }

    $.post(settings.submitUrl, $(this).serialize())
      .done(settings.submitSuccessHandler)
      .fail(function(data) {
        $(document).Toasts('create', {
          class: 'bg-danger',
          title: 'Error',
          subtitle: `Code ${data.responseJSON.code}`,
          body: data.responseJSON.message,
        });
      });
  });
}
