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
    const supportedParts = ['decimal', 'fraction', 'group', 'integer', 'minusSign', 'plusSign'];
    return parts.filter(p => supportedParts.indexOf(p.type) != -1).map(p => p.value).join('');
  }

  return {
    colorGain: colorGain,
    asCurrency: asCurrency,
    asCurrencyNumber: asCurrencyNumber,
  };
}();
