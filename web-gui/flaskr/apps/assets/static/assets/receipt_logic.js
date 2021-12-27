"use strict";

var formConst;
var formState = {
  updated: {
    price: false,
    unitPrice: false,
    volume: false
  }
};

function setupForm(initQuantity, currency, type) {
  formConst = {
    initQuantity: initQuantity,
    currency: currency,
    type: type,
  };

  $("#f-date").val(function(d){
    return d.getFullYear() + "-" + ("0"+(d.getMonth()+1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2) + " " +
      ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2) + ":" + ("0" + d.getSeconds()).slice(-2);
  }(new Date()));
}

$(function(){
  function updateQuantityAfter() {
    const quantity = $("#f-quantity");
    if (quantity.valid()) {
      const type = $("#f-type").val();
      const multiplier = (type == "SELL" ? -1 : 1);
      const quantityAfter = utils.float.parse(quantity) * multiplier + formConst.initQuantity;

      $("#f-quantity-after").val(utils.float.normalize(quantityAfter))
                            .valid();
    }
  }
  function updateQuantity() {
    const unitPrice = $("#f-unit-price");
    const price = $("#f-price");
    if (!unitPrice.valid() || !price.valid())
      return;

    $("#f-quantity").val(utils.float.normalize(utils.float.parse(price) / utils.float.parse(unitPrice))).valid();
  }
  function updatePrice() {
    const unitPrice = $("#f-unit-price");
    const quantity = $("#f-quantity");
    if (!quantity.valid() || !unitPrice.valid())
      return;

    $("#f-price").val(utils.float.normalize(utils.float.parse(unitPrice) * utils.float.parse(quantity))).valid();

  }
  function updateUnitPrice() {
    const price = $("#f-price");
    const quantity = $("#f-quantity");
    if (!quantity.valid() || !price.valid())
      return;

    $("#f-unit-price").val(utils.float.normalize(utils.float.parse(price) / utils.float.parse(quantity))).valid();
  }
  function quantityChanged() {
    updateQuantityAfter();

    if (formState.updated.price)
      updateUnitPrice();
    else
      updatePrice();
  }

  $("#f-quantity").on('focus', function(){
    if (!formState.updated.volume)
      $(this).val('');
  });
  $("#f-quantity").on('input', function(){
    formState.updated.volume = true;
    quantityChanged();
  });

  $("#f-type").change(function(){
    updateQuantityAfter();
    $("#f-quan-all").attr('disabled', $(this).val() != "SELL");
  });

  $("#f-price").on('input', function(){
    formState.updated.price = true;

    if (!formState.updated.quantity)
      updateQuantity();
    else
      updateUnitPrice();
  });

  $("#f-unit-price").on('input', function(){
    formState.updated.unitPrice = true;

    if (formState.updated.price)
      updateQuantity();
    else
      updatePrice();
  });

  $("#f-quan-all").click(function(){
    $("#f-quantity").val(formConst.initQuantity)
    quantityChanged();
  });

  function updateCost() {
    const provision = $("#f-provision");
    const conversion = $("#f-conversion");
    const type = $("#f-type");
    const price = formConst != 'Deposit' ? $("#f-price") : $("#f-quantity");

    if (type.valid() && price.valid() && provision.valid() && (!conversion.length || conversion.valid())) {
      const netPrice = utils.float.parse(conversion, 1.0) * utils.float.parse(price);

      const cost = function(){
        if (type.val() == "BUY")
          return netPrice + utils.float.parse(provision);
        if (type.val() == "SELL")
          return netPrice - utils.float.parse(provision);
        if (type.val() == "RECEIVE")
          throw "Did not implement RECEIVE";
        if (type.val() == "EARNING")
          throw "Did not implement EARNING";
      }();

      $("#f-cost").val(styling.asCurrencyNumber(cost, formConst.currency)).valid();
    }
  }

  $("#f-provision").on('input', updateCost);
  $("#f-conversion").on('input', updateCost);
  $("#f-quantity").on('input', updateCost);
  $("#f-price").on('input', updateCost);
  $("#f-unit-price").on('input', updateCost);
});
