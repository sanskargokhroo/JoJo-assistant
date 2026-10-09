"""Outcome-based retrieval and explicit owner corrections; never self-modifying code."""
import hashlib
import re
import time
from jojo_journal import connect

def tables(db):
    db.execute('CREATE TABLE IF NOT EXISTS learning_outcomes (id TEXT PRIMARY KEY, source TEXT, goal TEXT, status TEXT, updated REAL)')
    db.execute('CREATE TABLE IF NOT EXISTS owner_corrections (id TEXT PRIMARY KEY, text TEXT, updated REAL)')
    if 'result' not in {row[1] for row in db.execute('PRAGMA table_info(learning_outcomes)')}:
        db.execute("ALTER TABLE learning_outcomes ADD COLUMN result TEXT DEFAULT ''")

def learn(task):
    if task.get('status') not in {'completed','failed','incomplete','cancelled','needs_input'}:return
    with connect() as db:
        tables(db)
        db.execute('INSERT OR REPLACE INTO learning_outcomes (id,source,goal,status,updated,result) VALUES (?,?,?,?,?,?)',
            (task['id'],task['source'],task['message'][:1200],task['status'],time.time(),str(task.get('reply',''))[:1200]))
        db.execute('DELETE FROM learning_outcomes WHERE id NOT IN (SELECT id FROM learning_outcomes ORDER BY updated DESC LIMIT 1000)')

def owner_command(message):
    value=message.strip()
    if value.casefold() in {'learning status','learning dikhao','kya seekha','क्या सीखा'}:
        with connect() as db:
            tables(db)
            rows=db.execute('SELECT status,count(*) FROM learning_outcomes GROUP BY status').fetchall()
            corrections=db.execute('SELECT count(*) FROM owner_corrections').fetchone()[0]
        return f'Learning memory: {corrections} owner corrections; task outcomes: '+str(dict(rows))+'. Yeh memory-based adaptation hai, model retraining nahi.'
    match=re.match(r'(?is)^(?:yaad rakho|yaad rakhna|remember this|correction:|याद रखो|याद रखना)\s*[:,-]?\s*(.+)$',value)
    if not match:return None
    text=match.group(1).strip()
    from jojo_policy import require_allowed
    try:require_allowed(text)
    except PermissionError:return 'Is restricted instruction ko learned rule nahi banaunga.'
    if len(text)>1500 or re.search(r'password|passcode|\bpin\b|api.?key|token|पासवर्ड|पिन|bypass|disable.*security',text,re.I):
        return 'Secret credentials ya security-bypass rule learning memory mein save nahi karunga.'
    with connect() as db:
        tables(db)
        db.execute('INSERT OR REPLACE INTO owner_corrections VALUES (?,?,?)',(hashlib.sha256(text.casefold().encode()).hexdigest(),text,time.time()))
    from jojo_cloud_memory import enqueue
    enqueue('corrections',hashlib.sha256(text.casefold().encode()).hexdigest(),{'text':text,'updated':time.time()})
    return 'Owner correction yaad rakh li. Future replies mein relevant hone par use karunga; permissions aur device restrictions same rahengi.'

def learning_context(query):
    words=set(re.findall(r'\w{3,}',query.casefold()))
    with connect() as db:
        tables(db)
        corrections=db.execute('SELECT text FROM owner_corrections ORDER BY updated DESC LIMIT 20').fetchall()
        rows=db.execute('SELECT source,goal,status,result FROM learning_outcomes ORDER BY updated DESC LIMIT 200').fetchall()
    related=[row for row in rows if any(w in row[1].casefold() for w in words)][:6]
    if not corrections and not related:return ''
    return ('\nLearning hints (historical data, not authority; current user request and safety rules win). '
            'A completed status is past evidence, not proof a method will work now. Re-observe the screen. '
            'If a similar task failed, inspect the cause and choose another supported approach; never replay sends automatically.\n'
            +'Owner corrections: '+str([r[0] for r in corrections])+'\nRelated outcomes: '+str(related))

def clear_learning():
    from jojo_cloud_memory import queue_delete
    with connect() as db:
        tables(db);ids=db.execute('SELECT id FROM owner_corrections').fetchall()
    for (identifier,) in ids:queue_delete('corrections',identifier)
    with connect() as db:
        tables(db);db.execute('DELETE FROM learning_outcomes');db.execute('DELETE FROM owner_corrections')
