CREATE DATABASE authfastapi;
\c authfastapi

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    role VARCHAR(100) DEFAULT 'client',
    is_active BOOLEAN DEFAULT TRUE
);

