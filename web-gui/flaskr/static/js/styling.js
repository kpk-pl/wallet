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

  function asCurrencyNumber(value, currency) {
    const parts = Intl.NumberFormat(typing.locales, { style: 'currency', currency: currency }).formatToParts(value);
    const supportedParts = ['decimal', 'fraction', 'integer', 'minusSign', 'plusSign'];
    return parts.filter(p => supportedParts.indexOf(p.type) != -1).map(p => p.value).join('');
  }

  function operationColor(type) {
    if (type == 'BUY')
      return 'rgb(40, 167, 69)';
    if (type == 'SELL')
      return 'rgb(220, 53, 69)';
    if (type == 'RECEIVE')
      return 'rgb(146, 198, 3)';
    if (type == 'EARNING')
      return 'rgb(3, 20, 198)';
    return 'rgb(255, 255, 255)';
  }

  return {
    colorGain: colorGain,
    asCurrency: asCurrency,
    asCurrencyNumber: asCurrencyNumber,
    operationColor: operationColor,
  };
}();
