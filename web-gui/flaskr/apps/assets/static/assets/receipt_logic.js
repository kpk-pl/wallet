"use strict";

var formConst;
var formState = {
  updated: {
    price: false,
    unitPrice: false,
    volume: false
  }
};

function setupForm(initQuantity, currency, currencyDecimals) {
  formConst = {
    initQuantity: initQuantity,
    currency: currency,
    currencyDecimals: currencyDecimals
  };

  $("#f-date").val(function(d){
    return d.getFullYear() + "-" + ("0"+(d.getMonth()+1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2) + " " +
      ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2) + ":" + ("0" + d.getSeconds()).slice(-2);
  }(new Date()));
}

  function updateQuantity() {
    const quantity = $("#f-quantity");
    if (quantity.valid()) {
      const type = $("#f-type").val();
      const multiplier = (type == "SELL" ? -1 : 1);
      const quantityAfter = utils.float.parse(quantity) * multiplier + formConst.initQuantity;

      $("#f-quantity-after").val(utils.float.normalize(quantityAfter))
                            .valid();
    }
  }

  $("#f-quantity").on('input', updateQuantity)
  $("#f-type").change(updateQuantity)
  $("#f-type").change(() => $("#f-quan-all").attr('disabled', $(this).val() != "SELL"))

  function updateCost() {
    const provision = $("#f-provision")
    const conversion = $("#f-conversion")
    const type = $("#f-type").val()

    let price = $("#f-price")
    if (!price.length) {
      price = $("#f-quantity")
    }

    if (price.valid() && provision.valid() && (!conversion.length || conversion.valid())) {
      let cost = utils.float.parse(conversion, 1.0) * utils.float.parse(price)
      cost += (type == "ADD" ? 1 : -1) * utils.float.parse(provision)

      $("#f-cost").val(cost.toFixed(formConst.currencyDecimals)).valid()
    }
  }

  $("#f-price").on('input', function(){
    const quantity = $("#f-quantity");
    const price = $(this);
    if (quantity.valid() && price.valid()) {
      $("#f-unit-price").val((utils.float.parse(price) / utils.float.parse(quantity)).toFixed(formConst.currencyDecimals)).valid();
    }
  });

  $("#f-unit-price").on('input', function(){
    const quantity = $("#f-quantity");
    const unitprice = $(this);
    if (quantity.valid() && unitprice.valid()) {
      $("#f-price").val((utils.float.parse(unitprice) * utils.float.parse(quantity)).toFixed(formConst.currencyDecimals)).valid();
    }
  });

  function updatePrices() {
    const quantity = $("#f-quantity");
    if (!quantity.valid())
      return;

    const price = $("#f-price");
    const unitprice = $("#f-unit-price");
    if (!price.length || !unitprice.length) {
      return;
    }

    if (price.valid()) {
      unitprice.val((utils.float.parse(price) / utils.float.parse(quantity)).toFixed(formConst.currencyDecimals)).valid();
    } else if (unitprice.valid()) {
      price.val((utils.float.parse(unitprice) * utils.float.parse(quantity)).toFixed(formConst.currencyDecimals)).valid();
    }
  }

  $("#f-quantity").on('input', updatePrices);

  $("#f-quan-all").click(function(){
    $("#f-quantity").val(formConst.initQuantity)
    updateQuantity();
    updatePrices();
  })

  $("#f-provision").on('input', updateCost)
  $("#f-conversion").on('input', updateCost)
  $("#f-quantity").on('input', updateCost)
  $("#f-price").on('input', updateCost)
  $("#f-unit-price").on('input', updateCost)
