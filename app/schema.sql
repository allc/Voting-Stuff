-- Initialize the database

-- put something here, making sure you drop the tables first

DROP TABLE IF EXISTS Voters;
DROP TABLE IF EXISTS Configuration;

CREATE TABLE Voters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    voter_id    TEXT NOT NULL,
    email_hash  TEXT NOT NULL,

    UNIQUE (voter_id),
    UNIQUE (email_hash)
);

CREATE TABLE Configuration (
    id                 INTEGER PRIMARY KEY DEFAULT 0,
    voting_form_url    TEXT NOT NULL,
    form_voter_id_field TEXT NOT NULL
);

INSERT INTO Configuration (voting_form_url, form_voter_id_field) VALUES ('', '');
