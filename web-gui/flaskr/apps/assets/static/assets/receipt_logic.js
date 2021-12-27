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
    const type = $(this).val();

    updateQuantityAfter();

    $("#f-quan-all").attr('disabled', type != "SELL");

    $("#g-provision").attr('hidden', type == "RECEIVE");
    $("#g-cost").attr('hidden', type == "RECEIVE");
    $("#g-billing-asset").attr('hidden', type == "RECEIVE");

    $("#g-quantity").attr('hidden', type == "EARNING");
    $("#g-quantity-after").attr('hidden', type == "EARNING");
    $("#g-conversion").attr('hidden', type == "EARNING");
    $("#g-price").attr('hidden', type == "EARNING");
    $("#g-unit-price").attr('hidden', type == "EARNING");

    $("#g-earning").attr('hidden', type != "EARNING");
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
    const earning = $("#f-earning");
    const type = $("#f-type");
    const price = formConst != 'Deposit' ? $("#f-price") : $("#f-quantity");

    if (!type.valid())
      return;

    if (type.val() == "BUY") {
      if (price.valid() && provision.valid() && (!conversion.length || conversion.valid())) {
        const cost = utils.float.parse(conversion, 1.0) * utils.float.parse(price) + utils.float.parse(provision);
        $("#f-cost").val(styling.asCurrencyNumber(cost, formConst.currency)).valid();
      }
    }
    else if (type.val() == "SELL") {
      if (price.valid() && provision.valid() && (!conversion.length || conversion.valid())) {
        const cost = utils.float.parse(conversion, 1.0) * utils.float.parse(price) - utils.float.parse(provision);
        $("#f-cost").val(styling.asCurrencyNumber(cost, formConst.currency)).valid();
      }
    }
    else if (type.val() == "RECEIVE") {
      $("#f-cost").val(styling.asCurrencyNumber(0, formConst.currency)).valid();
    }
    else if (type.val() == "EARNING") {
      if (earning.valid() && provision.valid()) {
        const cost = utils.float.parse(earning) - utils.float.parse(provision);
        $("#f-cost").val(styling.asCurrencyNumber(cost, formConst.currency)).valid();
      }
    }
  }

  $("#f-provision").on('input', updateCost);
  $("#f-conversion").on('input', updateCost);
  $("#f-quantity").on('input', updateCost);
  $("#f-price").on('input', updateCost);
  $("#f-unit-price").on('input', updateCost);
  $("#f-earning").on('input', updateCost);
});
