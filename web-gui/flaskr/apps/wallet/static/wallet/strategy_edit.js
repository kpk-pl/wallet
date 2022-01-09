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
    node.info("add", node);

    if (node.isTopLevel()) {
      let newComponent = node.tree.rootNode.addChildren({
        title: "New component",
        percentage: 0,
        folder: true
      }, node.getNextSibling());
      newComponent.addChildren({title: "New mapping", percentage: 100});
      newComponent.setActive();
    }
    else {
      node.appendSibling({title: "New mapping", percentage: 100}).setActive();
    }
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
    extensions: ["edit", "table"],
    autoScroll: true,
    keyboard: false,
    aria: true,
    source: strategy,
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

      if (node.isTopLevel()) {
        if (node.isActive()) {
          tdList.eq(2)
                .html('<input class="form-control tree-aux-input" type="text" value="' + node.data.percentage + '">');
        }
        else {
          tdList.eq(2).text(node.data.percentage + '%');
        }
      }
      else {
        if (node.isActive()) {
          tdList.eq(1)
                .html('<input class="form-control tree-aux-input" type="text" value="' + node.data.percentage + '">');
        }
        else {
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
    edit: {
      triggerStart: ["clickActive", "f2", "mac+enter", "shift+click"],
    }
  });

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

//let lastClicked;

//$('.test1').click(function(e){
  //console.log("click");
	//if (lastClicked === this) {
  //console.log("second");
    //let html = $('<input type="text" value="' + this.textContent + '"></input>');
    //html.blur(function(){
      //let v = $(this).val();
			//$(this).parent().empty().text(v);
    //});
    //$(this).empty().append(html);
    //html.focus();
  //}
  //else {
    //lastClicked = this;
  //}
//});
