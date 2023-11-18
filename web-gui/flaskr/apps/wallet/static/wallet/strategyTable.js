class StrategyAssetAdjustmentTable {
  constructor(datatable, colMap) {
    this.datatable = datatable

    this.colMap = {}
    for (let key in colMap) {
      if (typeof colMap[key] == 'number')
        this.colMap[key] = {column: colMap[key], format: x => x}
      else
        this.colMap[key] = colMap[key]
    }
  }

  fillAssets(data) {
    if (data.assets == undefined)
      return;

    this.datatable.rows.add(data.assets)
    this.datatable.draw()
  }

  _adjustmentInRow(rowIdx) {
      const inputElement = this.datatable.cell(rowIdx, this.colMap.adjustment.column).node().getElementsByTagName('input')[0];
      return inputElement !== undefined ? Number(inputElement.value) : 0;
  }

  updateAdjustedValues() {
    let self = this;
    this.datatable.rows().every(function(rowIdx){
      const adjustment = self._adjustmentInRow(rowIdx);
      const unitValue = this.data().unitPrice * this.data().currencyConversion;
      self.datatable.cell(rowIdx, self.colMap.adjustedValue.column).data(self.colMap.adjustedValue.format(adjustment * unitValue));
    });

    this.datatable.draw();
  }

  collectAdjustments() {
    let adjustments = Object.create(null);
    
    let self = this;
    this.datatable.rows().every(function(rowIdx){
      const adjustment = self._adjustmentInRow(rowIdx);
      const unitValue = this.data().unitPrice * this.data().currencyConversion;

      if (!(this.data().category in adjustments))
        adjustments[this.data().category] = 0;

      adjustments[this.data().category] += adjustment * unitValue;
    });

    return adjustments;
  }
}

class StrategyTable {
  constructor(datatable, assetAdjustmentTable, colMap) {
    this.datatable = datatable
    this.assetAdjustmentTable = assetAdjustmentTable

    this.colMap = {}
    for (let key in colMap) {
      if (typeof colMap[key] == 'number')
        this.colMap[key] = {column: colMap[key], format: x => x}
      else
        this.colMap[key] = colMap[key]
    }
  }

  fillStrategy(data, rowCreator) {
    if (data.strategy == undefined)
      return;

    if (data.strategy.assetTypes.find(t=>t.name == "Others") == undefined)
      data.strategy.assetTypes.push({name: "Others", percentage: 0, categories:[]})

    for (let type of data.strategy.assetTypes) {
      this.datatable.row.add(rowCreator(type))
    }
    this.datatable.draw()
  }

  _collapseAllocation(allocation) {
    let result = Object.create(null)
    for (let category of Object.keys(allocation)) {
      for (let subcat of Object.keys(allocation[category])) {
        let key = category
        if (subcat && subcat != 'null') {
          key = subcat + ' ' + key
        }
        result[key] = parseFloat(allocation[category][subcat])
      }
    }
    return result
  }

  fillAllocation(data) {
    if (data.strategy === undefined || data.allocation === undefined)
      return;

    const allocation = this._collapseAllocation(data.allocation)
    let netValueRemaining = Object.keys(allocation).map(a=>allocation[a]).reduce((a,b)=>a+b)

    let self = this

    this.datatable.rows().every(function(rowIdx){
      let category = self.datatable.cell(rowIdx, self.colMap.name.column).data()
      let assetType = data.strategy.assetTypes.find(type => type.name == category);

      let netValue = 0;
      for (let category of assetType.categories) {
          let percentage = (typeof category == "string" ? 100 : category.percentage)
          let name = (typeof category == "string" ? category : category.name)
          if (name in allocation)
            netValue += parseFloat(allocation[name]) * percentage / 100
      }
      assetType.netValue = netValue
      netValueRemaining -= netValue
      self.datatable.cell(rowIdx, self.colMap.netValue.column).data(self.colMap.netValue.format(netValue))
    })

    let othersAsset = data.strategy.assetTypes.find(t=>t.name == "Others")
    othersAsset.netValue += netValueRemaining

    const othersRowIdx = this.datatable.row((_, data)=>data[this.colMap.name.column] == "Others").index()
    this.datatable.cell(othersRowIdx, this.colMap.netValue.column).data(this.colMap.netValue.format(othersAsset.netValue))

    this.datatable.draw()
  }

  _collectAssetAdjustments(strategy) {
    let adjustments = Object.create(null);
    for (const assetType of strategy.assetTypes) {
      adjustments[assetType.name] = 0;
    }

    if (this.assetAdjustmentTable === null)
      return adjustments;

    const assetAdjustments = this.assetAdjustmentTable.collectAdjustments();

    for (const assetType of strategy.assetTypes) {
      for (let category of assetType.categories) {
          let percentage = (typeof category == "string" ? 100 : category.percentage)
          let name = (typeof category == "string" ? category : category.name)
          if (name in assetAdjustments)
            adjustments[assetType.name] += assetAdjustments[name] * percentage / 100
      }
    }

    return adjustments
  }

  updateDeviation(data) {
    if (data.strategy === undefined || data.allocation === undefined)
      return;

    let self = this;
    const netValueSum = data.strategy.assetTypes.map(t=>t.netValue).reduce((a,b)=>a+b);
    const assetAdjustments = this._collectAssetAdjustments(data.strategy)

    function adjustValue(rowIdx) {
      if (self.colMap.netAdjust) {
        let inputElement = self.datatable.cell(rowIdx, self.colMap.netAdjust.column).node().getElementsByTagName('input')[0];
        return inputElement !== undefined ? Number(inputElement.value) : 0;
      }
      return 0;
    }

    let netAdjustSum = Object.values(assetAdjustments).reduce((a, b) => a + b, 0);
    this.datatable.rows().every(rowIdx => netAdjustSum += adjustValue(rowIdx));

    this.datatable.rows().every(function(rowIdx){
      const category = self.datatable.cell(rowIdx, self.colMap.name.column).data();
      const assetType = data.strategy.assetTypes.find(type => type.name == category);
      const value = assetType.netValue + adjustValue(rowIdx) + assetAdjustments[category];
      const percent = value / (netValueSum + netAdjustSum) * 100;
      const deviation = percent - assetType.percentage;
      self.datatable.cell(rowIdx, self.colMap.deviation.column).data(self.colMap.deviation.format(deviation) + '%');

      const targetValue = (netValueSum + netAdjustSum) * assetType.percentage / 100;
      const requiredChange = (targetValue - value) / (1-assetType.percentage/100);
      self.datatable.cell(rowIdx, self.colMap.requiredChange.column).data(self.colMap.requiredChange.format(requiredChange));
      if (self.colMap.rebalancingChange)
        self.datatable.cell(rowIdx, self.colMap.rebalancingChange.column).data(self.colMap.requiredChange.format(targetValue - value));
    })

    this.datatable.draw();
  }
}
