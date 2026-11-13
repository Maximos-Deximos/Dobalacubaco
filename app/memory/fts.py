# Criação da tabela virtual FTS5 usada na busca lexical.

from __future__ import annotations

from sqlalchemy.engine import Engine

# Objetos SQLite necessários para manter o índice lexical sincronizado.
CHUNK_FTS_STATEMENTS = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS source_chunks_fts USING fts5(
        text,
        section_title,
        page_number UNINDEXED,
        content='source_chunks',
        content_rowid='id',
        tokenize='unicode61 remove_diacritics 2'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS source_chunks_fts_ai
    AFTER INSERT ON source_chunks BEGIN
        INSERT INTO source_chunks_fts(rowid, text, section_title, page_number)
        VALUES (new.id, new.text, new.section_title, new.page_number);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS source_chunks_fts_ad
    AFTER DELETE ON source_chunks BEGIN
        INSERT INTO source_chunks_fts(
            source_chunks_fts,
            rowid,
            text,
            section_title,
            page_number
        )
        VALUES (
            'delete',
            old.id,
            old.text,
            old.section_title,
            old.page_number
        );
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS source_chunks_fts_au
    AFTER UPDATE ON source_chunks BEGIN
        INSERT INTO source_chunks_fts(
            source_chunks_fts,
            rowid,
            text,
            section_title,
            page_number
        )
        VALUES (
            'delete',
            old.id,
            old.text,
            old.section_title,
            old.page_number
        );
        INSERT INTO source_chunks_fts(rowid, text, section_title, page_number)
        VALUES (new.id, new.text, new.section_title, new.page_number);
    END
    """,
)


# Garante que a tabela FTS5 e os gatilhos existam no banco atual.
def ensure_chunk_fts(engine: Engine) -> None:
    with engine.begin() as connection:
        for statement in CHUNK_FTS_STATEMENTS:
            connection.exec_driver_sql(statement)
