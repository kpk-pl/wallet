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

rs.initiate({"_id": "rs", "version": 1, "members": [{"_id": 0, "priority": 2, "host": "mongo:27017"}]);
