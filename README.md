[![Actions Status](https://github.com/kpk-pl/wallet/workflows/Test%20web-gui/badge.svg?branch=master)](https://github.com/kpk-pl/wallet/actions/workflows/gui-tests.yml)
[![License](https://img.shields.io/badge/license-MIT-purple)](https://github.com/kpk-pl/wallet/blob/master/LICENSE)

# wallet

*wallet* is an investment tracking app.

## Deployment
### docker-compose

Ensure all services are enabled in docker-compose file. Simply run `docker-compose up -d`. This will initialize
your DB as well as build the GUI image. You can access MongoDB and GUI on ports that are defined in `docker-compose.yml`.

### Standalone

You still need MongoDB. Either use a subset of `docker-compose.yml` to have Mongo ready, or use local instance.
`bootstrap.sh` the GUI which will create Python's virtual env and install all dependencies. Then run `run.sh`
to start the application.

## Credits

- [AdminLTE](https://github.com/ColorlibHQ/AdminLTE) @ 3.1.0-rc
- [Bootstrap](https://getbootstrap.com/) @ 4.6.1
- [Bootstrap Tags Input](https://github.com/bootstrap-tagsinput/bootstrap-tagsinput) @ 0.8.0
- [bs-custom-file-input](https://github.com/Johann-S/bs-custom-file-input) @ 1.3.4
- [Chart.js](https://www.chartjs.org/) @ 3.6.2
- [chartjs-adapter-moment](https://github.com/chartjs/chartjs-adapter-moment) @ 1.0.0 
- [Datatables](https://www.datatables.net/) @ 1.10.23
- [Fancytree](https://github.com/mar10/fancytree) @ 2.38.0
- [Font Awesome](https://fontawesome.com/) 5.15.4
- [jQuery](https://jquery.com/) @ 3.5.1
- [jQuery Sparkline](https://plugins.jquery.com/sparkline/) @ 2.1.2
- [jQuery Validation Plugin](https://jqueryvalidation.org/) @ 1.19.3
- [Moment.js](https://momentjs.com/) @ 2.29.1
- [URI.js](http://medialize.github.io/URI.js/) @ 1.19.7
- [Tempus Dominus](https://getdatepicker.com/5-4/) @ 5.39.0
- [typeahead.js](https://github.com/twitter/typeahead.js) @ 0.11.1
