"""Explicit rollback of JoJo text-file edits, with encrypted originals and conflict checks."""
import hashlib
import threading
import time
import uuid
from pathlib import Path
from jojo_workspace import connect, private_session

_lock=threading.RLock()

def table(db):
    db.execute('CREATE TABLE IF NOT EXISTS undo_edits(id TEXT PRIMARY KEY,path TEXT,original BLOB,after_hash TEXT,created REAL)')

def write_text(path,content,append=False):
    path=Path(path).absolute()
    if path.is_symlink() or path.is_junction():raise ValueError('Linked files require manual editing.')
    path=path.resolve()
    with _lock:
        original=None
        if path.exists() and not private_session() and path.suffix.lower() in ('.txt','.md','.json','.csv') and path.stat().st_size<=2_000_000:
            if path.is_symlink() or path.resolve()!=path:
                raise ValueError('Linked paths require manual editing.')
            original=path.read_bytes()
        encrypted=None
        if original is not None:
            from jojo_user_config import protect
            encrypted=protect(original)
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a' if append else 'w',encoding='utf-8') as stream:stream.write(content)
        identifier=''
        if encrypted is not None:
            identifier=uuid.uuid4().hex
            with connect() as db:
                table(db)
                db.execute('INSERT INTO undo_edits VALUES(?,?,?,?,?)',(identifier,str(path),encrypted,hashlib.sha256(path.read_bytes()).hexdigest(),time.time()))
                db.execute('DELETE FROM undo_edits WHERE id NOT IN (SELECT id FROM undo_edits ORDER BY created DESC LIMIT 30)')
        return {'path':str(path),'bytes':path.stat().st_size,'undo_id':identifier}

def history():
    with connect() as db:
        table(db)
        return [dict(row) for row in db.execute('SELECT id,path,created FROM undo_edits ORDER BY created DESC')]

def restore(identifier):
    from jojo_capabilities import enabled
    from jojo_policy import require_allowed
    from jojo_user_config import protect
    if not enabled('files'):raise PermissionError('File access is disabled.')
    with _lock,connect() as db:
        table(db);row=db.execute('SELECT * FROM undo_edits WHERE id=?',(identifier,)).fetchone()
        if not row:raise ValueError('Undo entry not found or already used.')
        path=Path(row['path']);require_allowed(str(path))
        if not path.is_file() or path.is_symlink() or path.resolve()!=path or hashlib.sha256(path.read_bytes()).hexdigest()!=row['after_hash']:
            raise ValueError('File changed or moved since JoJo edited it. Undo refused to preserve newer work.')
        original=protect(row['original'],decrypt=True)
        path.write_bytes(original)
        if path.read_bytes()!=original:raise OSError('Restoration could not be verified.')
        db.execute('DELETE FROM undo_edits WHERE id=?',(identifier,))
        return {'restored':str(path),'verified':True}
