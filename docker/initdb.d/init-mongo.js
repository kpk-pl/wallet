db.auth('admin', 'password')
db = db.getSiblingDB('admin')

db.createUser({
  user: 'investing',
  pwd: 'investing',
  roles: [
    {
      role: 'readWrite',
      db: 'wallet'
    }
  ]
});


db = db.getSiblingDB('wallet')

/*
 * db.assets.insertMany([{field: "value"}])
 * db.currencies.insertMany([{field: "value"}])
 */


/*
The replicaset needs to be initialized for the transactions queries to work. However it is apparently not
possible to initialize the replicaset in the init script. Issue the below command after you first create an empty
mongo container. This can be even done through the shell in the MongoDB Compass

rs.initiate({"_id": "rs", "version": 1, "members": [{"_id": 0, "priority": 2, "host": "mongo:27017"}]});
*/
