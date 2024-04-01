-- Initialize the database

-- put something here, making sure you drop the tables first

DROP TABLE IF EXISTS Voters;
DROP TABLE IF EXISTS Configuration;
DROP TABLE IF EXISTS Questions;
DROP TABLE IF EXISTS Answers;

CREATE TABLE Voters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    voter_id    TEXT NOT NULL,
    email_hash  TEXT NOT NULL,
    voted_at    DATETIME DEFAULT NULL,

    UNIQUE (voter_id),
    UNIQUE (email_hash)
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
    voter_id    TEXT NOT NULL,
    question_id TEXT NOT NULL,
    answer      TEXT,

    FOREIGN KEY (voter_id) REFERENCES Voters(voter_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES Questions(question_id)
);

CREATE TABLE Configuration (
    id                 INTEGER PRIMARY KEY DEFAULT 0,
    voting_form_url    TEXT NOT NULL,
    form_voter_id_field TEXT NOT NULL
);

INSERT INTO Configuration (voting_form_url, form_voter_id_field) VALUES ('', '');
