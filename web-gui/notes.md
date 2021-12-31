## Resources

- https://codersdiaries.com/blog/flask-project-structure
- https://adminlte.io/docs/3.1//index.html

### Styling

#### Column visibility button (colvis)

To simply add a class to the button use this pattern while initializing `DataTable`:

```
buttons: [{
  extend: "colvis", className: "btn-xs btn-default"
}]
```

To customize it more a more complex pattern needs to be used:

```
buttons: {
  buttons: [
    { extend: "colvis", className: "btn-secondary btn-sm pb-0 pt-0" }
  ],
  dom: {
    button: { className: "btn" }
  },
}
```

The options here override the defauts specified in `static/plugins/datatables-buttons/js/buttons.bootstrap4.js:38`.

#### Search box for DataTable

Use first answer to the
[question](https://stackoverflow.com/questions/19274028/changing-dom-element-position-of-searchbox-in-datatables)
