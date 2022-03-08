"use strict";

var settings;
function initialize(s) {
  settings = s;
  settings.btnTrash = function(e){
    const key = $(e).attr('data-treenode-key');
    const node = $.ui.fancytree.getTree("#treeTable").getNodeByKey(key);
    //node.info("trash", node);

    if (node.getParent().countChildren() == 1)
      node.getParent().remove();
    else
      node.remove();
  };
  settings.btnAdd = function(e){
    const key = $(e).attr('data-treenode-key');
    const node = $.ui.fancytree.getTree("#treeTable").getNodeByKey(key);
    //node.info("add", node);

    if (node.isTopLevel()) {
      let newComponent = node.tree.rootNode.addChildren({
        title: "New strategy component",
        percentage: 0,
        folder: true
      }, node.getNextSibling());
      newComponent.addChildren({title: "New constituent category", percentage: 100});
      newComponent.setActive();
    }
    else {
      node.appendSibling({title: "New constituent category", percentage: 100}).setActive();
    }
  };
  settings.genericAdd = function(){
    const rootNode = $.ui.fancytree.getTree("#treeTable").rootNode;
    //node.info("genericAdd", rootNode);

    let newComponent = rootNode.addChildren({
      title: "New strategy component",
      percentage: 0,
      folder: true
    });
    newComponent.addChildren({title: "New constituent category", percentage: 100});
    newComponent.setActive();
  };
}

$(function(){
  let strategy = settings.data.assetTypes.map(function(at){
    return {
      title: at.name,
      folder: true,
      percentage: at.percentage,
      children: at.categories.map(function(cat){
        return {
          title: (typeof cat === 'object') ? cat.name : cat,
          percentage: (typeof cat === 'object') ? cat.percentage : 100,
        }
      }),
    }
  });

  $("#treeTable").fancytree({
    extensions: ["table"],
    autoScroll: true,
    keyboard: false,
    aria: true,
    source: strategy,
    nodata: false,
    table: {
      nodeColumnIdx: 0,
      indentation: 50,
    },
		renderNode: function (event, data) {
      //data.node.info(event.type, data);
      const node = data.node;
      const nodeSpan = $(node.span);

      if (!nodeSpan.data('rendered')) {
        let buttons = $(
        '<span class="treeNodeButtons">' +
          '<i data-treenode-key="'+node.key+'" onclick="settings.btnTrash(this)" class="text-danger fas fa-trash-alt"></i>' +
          '<i data-treenode-key="'+node.key+'" onclick="settings.btnAdd(this)" class="text-success fas fa-plus-square"></i>' +
        '</span>');
        nodeSpan.append(buttons);
        buttons.hide();
        nodeSpan.hover(()=>buttons.show(), ()=>buttons.hide())
        nodeSpan.data('rendered', true);
      }
		},
    renderColumns: function(event, data) {
      //data.node.info(event.type, data);
      const node = data.node;
      const tr = $(node.tr);
      const tdList = tr.find(">td");

      const titleElement = tdList.eq(0).children('span').children('.fancytree-title');
      if (node.isTopLevel()) {
        if (node.isActive()) {
          titleElement.html(`<input class="form-control tree-aux-title" type="text" value="${node.title}">`);
          tdList.eq(2).html('<input class="form-control tree-aux-input" type="text" value="' + node.data.percentage + '">');
        }
        else {
          //titleElement.text(node.title);
          tdList.eq(2).text(node.data.percentage + '%');
        }
      }
      else {
        if (node.isActive()) {
          titleElement.html(`<input class="form-control tree-aux-title" type="text" value="${node.title}">`);
          tdList.eq(1).html('<input class="form-control tree-aux-input" type="text" value="' + node.data.percentage + '">');
        }
        else {
          //titleElement.text(node.title);
          tdList.eq(1).text(node.data.percentage + '%');
        }
      }
    },
    activate: function(event, data) {
      //data.node.info(event.type, data);
      const node = data.node;

      if (node.isTopLevel()) {
        node.setExpanded(true);
      }

      //data.node.renderTitle();
      node.render(true);
    },
    deactivate: function(event, data) {
      //data.node.info(event.type, data.node.isActive(), data);
      const node = data.node;
      if (node.tr === null)
        return;

      const tdList = $(node.tr).find(">td");
      const titleElement = tdList.eq(0).children('span').children('.fancytree-title');
      node.title = titleElement.find("input")[0].value;

      if (node.isTopLevel()) {
        node.data.percentage = parseFloat(tdList.eq(2).find("input")[0].value)
        node.setExpanded(false);
      }
      else {
        node.data.percentage = parseFloat(tdList.eq(1).find("input")[0].value)
        node.parent.setExpanded(false);
      }

      node.render(true);
    },
  });

  $('#button-add').click(settings.genericAdd);

  $('#submit').click(function(){
    const tree = $.ui.fancytree.getTree("#treeTable");

    const data = tree.toDict(true).children.map(o => {
      return {
        name: o.title,
        percentage: o.data.percentage,
        categories: o.children.map(c => {
          return {
            name: c.title,
            percentage: c.data.percentage
          };
        })
      };
    });

    $.ajax(settings.submitUrl, {
      data: JSON.stringify(data),
      contentType: 'application/json',
      type: 'POST',
      success: function(){
        $(location).attr("href", settings.submitUrl);
      }
    });
  });
});
