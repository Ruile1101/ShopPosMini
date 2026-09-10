import sqlite3
from pathlib import Path

db = Path('pos.db')
print('db exists:', db.exists())
if db.exists():
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    print('sale rows:', con.execute("select count(*) as c from sale").fetchone()['c'])
    sale_cols = [r['name'] for r in con.execute("pragma table_info(sale)")]
    print('sale columns:', ','.join(sale_cols))
    user_cols = [r['name'] for r in con.execute("pragma table_info(user)")]
    print('user columns:', ','.join(user_cols))
    try:
        print('miss user ids:', con.execute("select id, user_id, customer_name, document_type from sale where user_id not in (select id from user)").fetchmany(20))
    except Exception as exc:
        print('missing-user query failed:', repr(exc))
    print('sample sales:', con.execute("select id, user_id, customer_name, document_type from sale order by id desc limit 10").fetchall())
