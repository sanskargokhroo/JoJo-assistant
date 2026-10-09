"""Opt-in routine scheduler: no catch-up replay after restart, no parallel runs."""
import threading
import time
from jojo_workspace import connect, routine_prompt, private_session

def table(db):
    db.execute('CREATE TABLE IF NOT EXISTS schedules(routine_id TEXT PRIMARY KEY, interval_seconds INTEGER, next_run REAL, last_task TEXT)')

def schedule(identifier,minutes):
    if type(minutes) is not int or not 5<=minutes<=10080:raise ValueError('Choose 5–10080 minutes.')
    if private_session():raise ValueError('Disable private session before scheduling.')
    routine_prompt(identifier)
    with connect() as db:
        table(db)
        db.execute('INSERT OR REPLACE INTO schedules VALUES(?,?,?,?)',(identifier,minutes*60,time.time()+minutes*60,''))

def unschedule(identifier):
    with connect() as db:
        table(db);db.execute('DELETE FROM schedules WHERE routine_id=?',(identifier,))

def schedules():
    with connect() as db:
        table(db);return [dict(row) for row in db.execute('SELECT * FROM schedules')]

def tick(manager,now=None):
    now=time.time() if now is None else now
    with connect() as db:
        table(db)
        due=db.execute('SELECT * FROM schedules WHERE next_run<=?',(now,)).fetchall()
        for row in due:
            # Claim once before submit. Interrupted claims are skipped, never replayed.
            if db.execute('UPDATE schedules SET next_run=? WHERE routine_id=? AND next_run=?',
                          (now+row['interval_seconds'],row['routine_id'],row['next_run'])).rowcount!=1:continue
            if private_session():continue
            previous=manager.get(row['last_task']) if row['last_task'] else None
            if previous and previous['status'] in ('queued','running'):continue
            try:
                prompt=routine_prompt(row['routine_id'])
            except ValueError:
                db.execute('DELETE FROM schedules WHERE routine_id=?',(row['routine_id'],));continue
            # Submit outside the SQLite transaction: journal writes may need the same database.
            yield row['routine_id'],prompt

def run_due(manager):
    due=list(tick(manager))
    for identifier,prompt in due:
        try:
            # Recheck a routine disabled or edited after the due list was claimed.
            prompt=routine_prompt(identifier)
            if private_session():continue
            if not any(row['routine_id']==identifier for row in schedules()):continue
            result=manager.submit(prompt,'laptop',False)
        except Exception as exc:
            with connect() as db:db.execute('UPDATE schedules SET last_task=? WHERE routine_id=?',('Skipped: '+type(exc).__name__,identifier))
            continue  # Missed runs are intentionally not retried.
        with connect() as db:
            db.execute('UPDATE schedules SET last_task=? WHERE routine_id=?',(result['id'],identifier))

def start(manager,stop):
    with connect() as db:
        table(db)
        db.execute('UPDATE schedules SET next_run=?+interval_seconds',(time.time(),))
    def worker():
        while not stop.wait(10):
            try:run_due(manager)
            except Exception:pass
    threading.Thread(target=worker,daemon=True,name='JoJo reviewed routines').start()
