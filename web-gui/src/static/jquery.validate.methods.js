jQuery.validator.addMethod("greaterThan", function(value, element, params) {
  return parseFloat(value) > params;
}, 'Please enter a value greater than {0}.');

jQuery.validator.addMethod("isDate", function(value, element, params) {
  if (!params)
    return true;

  return !/Invalid|NaN/.test(new Date(value));
}, 'Please enter a valid date.');
