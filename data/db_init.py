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
        set_id varchar references sets(id),
        name varchar NOT NULL,
        hp int,
        body text,
        set_code varchar,
        number_in_set varchar,
        rarity varchar,
        image_url varchar,
        tcgplayer_price numeric,
        cardmarket_price numeric,
        last_price_update timestamp
    );

    CREATE TABLE user_cards (
        id uuid PRIMARY KEY,
        user_id uuid references users(id) NOT NULL,
        card_id varchar references cards(id) NOT NULL,
        quantity int default 1,
        condition varchar default 'near_mint',
        notes text,
        scanned_image_url varchar,
        created_at timestamp default CURRENT_TIMESTAMP
    );
"""

cursor_obj.executescript(table_creation_query)
print("Tables created successfully")

connection_obj.close()
