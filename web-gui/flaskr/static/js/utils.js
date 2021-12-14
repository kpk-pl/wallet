const utils = (function(){
  function parseFloatWithDefault(param, def = 0.0) {
    const res = parseFloat(param.val());
    return isNaN(res) ? def : res;
  }

  return {
    float: {
      parse: parseFloatWithDefault,
      normalize: x => parseFloat(x.toFixed(10))
    }
  };
})();
