class StrategyTable {
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

  fillStrategy(data, rowCreator) {
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
          key += ' ' + subcat
        }
        result[key] = allocation[category][subcat]
      }
    }
    return result
  }

  fillAllocation(data) {
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
            netValue += allocation[name] * percentage / 100
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

  updateDeviation(data) {
    let self = this

    const netValueSum = data.strategy.assetTypes.map(t=>t.netValue).reduce((a,b)=>a+b)

    const adjustValue = function(rowIdx){
      if ('netAdjust' in self.colMap)
        return Number(self.datatable.cell(rowIdx, self.colMap.netAdjust.column).node().getElementsByTagName('input')[0].value)
      return 0
    }

    let netAdjustSum = 0
    this.datatable.rows().every(function(rowIdx){
      netAdjustSum += adjustValue(rowIdx)
    })

    this.datatable.rows().every(function(rowIdx){
      let category = self.datatable.cell(rowIdx, self.colMap.name.column).data()
      let assetType = data.strategy.assetTypes.find(type => type.name == category);
      let value = assetType.netValue + adjustValue(rowIdx)
      let percent = value / (netValueSum + netAdjustSum) * 100
      let deviation = percent - assetType.percentage
      self.datatable.cell(rowIdx, self.colMap.deviation.column).data(self.colMap.deviation.format(deviation) + '%')

      let targetValue = (netValueSum + netAdjustSum) * assetType.percentage / 100
      //let requiredChange = targetValue - value
      let requiredChange = (targetValue - value) / (1-assetType.percentage/100)
      self.datatable.cell(rowIdx, self.colMap.requiredChange.column).data(self.colMap.requiredChange.format(requiredChange))
    })

    this.datatable.draw()
  }
}
