const styling = function(){
  function colorGain() {
    if ($(this).text().startsWith('-')) {
      $(this).addClass('color-gain-negative')
    } else {
      $(this).addClass('color-gain-positive')
    }
  }

  return {
    colorGain: colorGain
  };
}();
