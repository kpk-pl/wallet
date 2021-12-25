const styling = function(){
  function colorGain() {
    if ($(this).text().startsWith('-')) {
      $(this).addClass('color-gain-negative')
    } else {
      $(this).addClass('color-gain-positive')
    }
  }

  function asCurrency(value, currency) {
    return new Intl.NumberFormat(typing.locales, { style: 'currency', currency: currency }).format(value);
  }

  return {
    colorGain: colorGain,
    asCurrency: asCurrency
  };
}();
