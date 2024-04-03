-- Initialize the database

-- put something here, making sure you drop the tables first

DROP TABLE IF EXISTS Voters;
DROP TABLE IF EXISTS Configuration;
DROP TABLE IF EXISTS Questions;
DROP TABLE IF EXISTS Answers;
DROP TABLE IF EXISTS Stats;

CREATE TABLE Voters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    voter_id_hash    TEXT NOT NULL,
    voted_at    DATETIME DEFAULT NULL,

    UNIQUE (voter_id_hash)
);

CREATE TABLE Questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id TEXT NOT NULL,
    question    TEXT,
    question_type TEXT,

    UNIQUE (question_id)
);

CREATE TABLE Answers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    voter_id_hash    TEXT NOT NULL,
    question_id TEXT NOT NULL,
    answer      TEXT,

    FOREIGN KEY (voter_id_hash) REFERENCES Voters(voter_id_hash) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES Questions(question_id)
);

CREATE TABLE Configuration (
    id                 INTEGER PRIMARY KEY DEFAULT 0,
    voting_form_url    TEXT NOT NULL,
    form_voter_id_field TEXT NOT NULL
);

INSERT INTO Configuration (voting_form_url, form_voter_id_field) VALUES ('', '');

CREATE TABLE Stats (
    id          INTEGER PRIMARY KEY DEFAULT 0,
    form_received_count INTEGER DEFAULT 0,
    form_accepted_count INTEGER DEFAULT 0,
    form_rejected_count INTEGER DEFAULT 0
);

INSERT INTO Stats (form_received_count, form_accepted_count, form_rejected_count) VALUES (0, 0, 0);
