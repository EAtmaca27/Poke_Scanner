import sqlite3


connection_obj = sqlite3.connect('pokemon.db')

cursor_obj = connection_obj.cursor()

cursor_obj.execute("DROP TABLE IF EXISTS pokemon")

table_creation_query = """
    CREATE TABLE users (
        id uuid PRIMARY KEY,
        username varchar NOT NULL,
        password text NOT NULL,
        created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE sets (
        id varchar PRIMARY KEY,
        name varchar NOT NULL,
        set_code varchar NOT NULL,
        release_date date,
        total_cards int,
        symbol_url varchar
    );

    CREATE TABLE cards (
        id varchar PRIMARY KEY,
        name varchar NOT NULL,
        hp int ,
        body text,
        set_code varchar NOT NULL,
        number_in_set varchar NOT NULL,
        rarity varchar,
        quantity int DEFAULT 0,
        set_id varchar REFERENCES sets(id),
        image_url varchar,
        tcgplayer_price numeric,
        cardmarket_price numeric,
        last_price_update timestamp
    );

    CREATE TABLE user_cards (
        user_id uuid REFERENCES users(id) NOT NULL,
        card_id varchar REFERENCES cards(id) NOT NULL,
        quantity int DEFAULT 1,
        condition varchar DEFAULT 'Near Mint',
        notes text,
        scanned_image_url varchar,
        created_at timestamp DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, card_id, condition)
    );

    CREATE TABLE scan_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id uuid REFERENCES users(id) NOT NULL,
        scan_type varchar NOT NULL,
        model varchar,
        input_tokens int,
        output_tokens int,
        total_tokens int,
        duration_ms int,
        extracted_name varchar,
        extracted_hp varchar,
        extracted_number varchar,
        created_at timestamp DEFAULT CURRENT_TIMESTAMP
    );
"""

cursor_obj.executescript(table_creation_query)
print("Tables created successfully")
connection_obj.close()
print("Connection closed")