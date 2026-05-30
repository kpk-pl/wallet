"use strict";

// Wires up the shared parametrized-pricing editor (#form-parametrized) used by
// both the asset add and edit pages. `settings` provides headerLabels, the
// submitUrl to POST the JSON payload to, and getNextUrl(data) for redirection.
function initParametrizedForm(settings) {
  const $form = $('#form-parametrized');
  if ($form.length === 0) return;

  $('#p-labels').tagsinput({
    tagClass: 'badge badge-success',
    typeaheadjs: {
      source: function(query, sync){ sync(settings.headerLabels); }
    }
  });

  function showError(message, code){
    $(document).Toasts('create', {
      class: 'bg-danger',
      title: 'Error',
      subtitle: code !== undefined ? `Code ${code}` : '',
      body: message,
    });
  }

  function renumberPeriods(){
    $('#p-interest-list .interest-period').each(function(idx){
      $(this).find('.interest-period-title').text('Period ' + (idx + 1));
    });
  }

  function addInterestPeriod(){
    const template = document.getElementById('p-interest-template');
    $('#p-interest-list').append(document.importNode(template.content, true));
    renumberPeriods();
  }

  $('#p-add-interest').click(addInterestPeriod);

  $('#p-interest-list')
    .on('change', '.p-fixed-enable', function(){
      $(this).closest('.interest-period').find('.p-fixed-fields').toggle(this.checked);
    })
    .on('change', '.p-derived-enable', function(){
      $(this).closest('.interest-period').find('.p-derived-fields').toggle(this.checked);
    })
    .on('click', '.p-remove-interest', function(){
      if ($('#p-interest-list .interest-period').length <= 1) return;
      $(this).closest('.interest-period').remove();
      renumberPeriods();
    });

  // The edit page renders the asset's existing periods server-side; the add page
  // starts empty, so seed a single fixed-rate period to edit from.
  if ($('#p-interest-list .interest-period').length === 0) {
    addInterestPeriod();
    $('#p-interest-list .p-fixed-enable').prop('checked', true).trigger('change');
  } else {
    renumberPeriods();
  }

  function buildPayload(){
    const interest = [];
    $('#p-interest-list .interest-period').each(function(){
      const $period = $(this);
      const item = {};

      if ($period.find('.p-fixed-enable').is(':checked')) {
        item.fixed = { percentage: $period.find('.p-fixed-pct').val() };
      }

      if ($period.find('.p-derived-enable').is(':checked')) {
        const sample = {
          interval: $period.find('.p-derived-interval').val(),
          intervalOffset: parseInt($period.find('.p-derived-offset').val() || '0', 10),
          choose: $period.find('.p-derived-choose').val(),
          multiplier: $period.find('.p-derived-multiplier').val() || '1',
          usePreviousWhenMissing: $period.find('.p-derived-useprev').is(':checked'),
        };
        const clampBelow = $period.find('.p-derived-clamp').val();
        if (clampBelow !== '') sample.clampBelow = clampBelow;

        item.derived = { quoteId: $period.find('.p-derived-quote').val(), sample: sample };
      }

      interest.push(item);
    });

    return {
      kind: 'parametrized',
      name: $('#p-name').val(),
      institution: $('#p-institution').val(),
      type: $('#p-type').val(),
      category: $('#p-category').val(),
      subcategory: $('#p-subcategory').val() || null,
      region: $('#p-region').val() || null,
      link: $('#p-link').val() || null,
      currency: $('#p-currency').val(),
      labels: $('#p-labels').val(),
      pricing: {
        length: {
          count: parseInt($('#p-length-count').val(), 10),
          name: $('#p-length-name').val(),
          multiplier: parseInt($('#p-length-multiplier').val() || '1', 10),
        },
        profitDistribution: $('#p-profit-distribution').val(),
        interest: interest,
      },
    };
  }

  $form.on('submit', function(event){
    event.preventDefault();

    const form = this;
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    const $periods = $('#p-interest-list .interest-period');
    if ($periods.length === 0) {
      showError('Add at least one interest period');
      return;
    }

    let error = null;
    $periods.each(function(){
      const $period = $(this);
      const hasFixed = $period.find('.p-fixed-enable').is(':checked');
      const hasDerived = $period.find('.p-derived-enable').is(':checked');
      if (!hasFixed && !hasDerived) {
        error = error || 'Each interest period needs a fixed and/or a derived rate';
      }
      if (hasFixed && !$period.find('.p-fixed-pct').val()) {
        error = error || 'Fixed rate value is required';
      }
      if (hasDerived && !$period.find('.p-derived-quote').val()) {
        error = error || 'Derived rate needs a quote source';
      }
    });
    if (error) {
      showError(error);
      return;
    }

    $.ajax({
      url: settings.submitUrl,
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify(buildPayload()),
    })
      .done(function(data){
        $(location).attr('href', settings.getNextUrl(data));
      })
      .fail(function(data){
        const message = (data.responseJSON && data.responseJSON.message) || 'Request failed';
        const code = data.responseJSON && data.responseJSON.code;
        showError(message, code);
      });
  });
}
