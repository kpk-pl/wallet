# Investment tracking app

## Deployment
### docker-compose

Ensure all services are enabled in docker-compose file. Simply run `docker-compose up -d`. This will initialize
your DB as well as build the GUI image. You can access MongoDB and GUI on ports that are defined in `docker-compose.yml`.

### Standalone

You still need MongoDB. Either use a subset of `docker-compose.yml` to have Mongo ready, or use local instance.
`bootstrap.sh` the GUI which will create Python's virtual env and install all dependencies. Then run `run.sh`
to start the application.

