// Executed automatically by the mongo:7 image on first startup
// Creates application-level users and roles


const adminDb = db.getSiblingDB('admin');


// app database name
const APP_DB = 'meddb';


// Create an ingestor user (writes + can create indexes)
adminDb.createUser({
    user: 'ingestor',
    pwd: 'ingestorpass',
    roles: [
    { role: 'readWrite', db: APP_DB },
    { role: 'dbAdmin', db: APP_DB },
    ],
});


// Read-only user for analysts
adminDb.createUser({
    user: 'analyst',
    pwd: 'analystpass',
    roles: [
    { role: 'read', db: APP_DB },
    ],
});