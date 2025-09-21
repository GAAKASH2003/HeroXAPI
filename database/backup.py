import sqlite3, shutil, os, uuid, sys
DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'app.db')
BACKUP = DB + '.bak'
if not os.path.exists(DB):
    print("DB not found:", DB); sys.exit(1)
shutil.copy2(DB, BACKUP)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
try:
    cur.execute("PRAGMA foreign_keys=OFF;")
    # read existing phishlets
    cur.execute("SELECT * FROM phishlets;")
    rows = cur.fetchall()
    id_map = {}
    for r in rows:
        old = r['id']
        new = str(uuid.uuid4())
        id_map[old] = new
    # create new phishlets table with text id and temporary old_id to map
    cur.execute("""
    CREATE TABLE phishlets_new (
      id TEXT PRIMARY KEY,
      name TEXT,
      description TEXT,
      user_id INTEGER,
      original_url TEXT,
      clone_url TEXT,
      html_content TEXT,
      form_fields TEXT,
      capture_credentials INTEGER,
      capture_other_data INTEGER,
      redirect_url TEXT,
      is_active INTEGER,
      created_at DATETIME,
      updated_at DATETIME
    );
    """)
    for r in rows:
        cur.execute("INSERT INTO phishlets_new (id,name,description,user_id,original_url,clone_url,html_content,form_fields,capture_credentials,capture_other_data,redirect_url,is_active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (id_map[r['id']], r['name'], r['description'], r['user_id'], r['original_url'], r['clone_url'], r['html_content'], r['form_fields'], r['capture_credentials'], r['capture_other_data'], r['redirect_url'], r['is_active'], r['created_at'], r['updated_at']))
    # create campaigns_new and copy mapping phishlet_id -> new uuid
    cur.execute("""
    CREATE TABLE campaigns_new (
      id INTEGER PRIMARY KEY,
      name TEXT,
      description TEXT,
      user_id INTEGER,
      sender_profile_id INTEGER,
      email_template_id INTEGER,
      phishlet_id TEXT,
      target_type TEXT,
      target_group_id INTEGER,
      target_individuals TEXT,
      scheduled_at DATETIME,
      status TEXT,
      is_active INTEGER,
      created_at DATETIME,
      updated_at DATETIME,
      FOREIGN KEY(phishlet_id) REFERENCES phishlets(id)
    );
    """)
    cur.execute("SELECT * FROM campaigns;")
    camps = cur.fetchall()
    for c in camps:
        old_ph = c['phishlet_id']
        new_ph = id_map.get(old_ph)
        cur.execute("INSERT INTO campaigns_new (id,name,description,user_id,sender_profile_id,email_template_id,phishlet_id,target_type,target_group_id,target_individuals,scheduled_at,status,is_active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (c['id'], c['name'], c['description'], c['user_id'], c['sender_profile_id'], c['email_template_id'], new_ph, c['target_type'], c['target_group_id'], c['target_individuals'], c['scheduled_at'], c['status'], c['is_active'], c['created_at'], c['updated_at']))
    # drop old and rename
    cur.execute("DROP TABLE phishlets;")
    cur.execute("ALTER TABLE phishlets_new RENAME TO phishlets;")
    cur.execute("DROP TABLE campaigns;")
    cur.execute("ALTER TABLE campaigns_new RENAME TO campaigns;")
    conn.commit()
    print("Migration OK. Backup at:", BACKUP)
except Exception as e:
    conn.rollback()
    shutil.copy2(BACKUP, DB)
    print("Migration failed, restored backup. Error:", e)
finally:
    cur.execute("PRAGMA foreign_keys=ON;")
    conn.close()