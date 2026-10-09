"""Erase the explicitly confirmed JoJo Firestore collections after workers stop."""
from pathlib import Path

LEGACY = ('user_profile', 'learned_skills', 'conversations', 'notes', 'reminders', 'jojo_remote_commands')

def erase_collection(collection):
    # Firestore document deletion does not remove nested collections.
    while True:
        documents = list(collection.limit(100).stream(timeout=15, retry=None))
        if not documents:
            return
        for document in documents:
            for child in document.reference.collections():
                erase_collection(child)
            document.reference.delete(timeout=15, retry=None)

def erase(client, namespace):
    shared = client.collection('jojo_memory').document(namespace)
    for kind in ('turns', 'workflows', 'corrections'):
        erase_collection(shared.collection(kind))
    # Include any nested data in this explicitly selected namespace.
    for child in shared.collections():
        erase_collection(child)
    shared.delete(timeout=15, retry=None)
    for name in LEGACY:
        erase_collection(client.collection(name))

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--confirmed-erase-jojo', action='store_true', required=True)
    parser.parse_args()
    from jojo_config import ROOT
    from jojo_cloud_memory import namespace
    import firebase_admin
    from firebase_admin import credentials, firestore
    from jojo_config import firebase_credential
    key=firebase_credential()
    if not key:
        raise RuntimeError('Firestore key missing; cloud deletion cannot be verified.')
    app=firebase_admin.initialize_app(credentials.Certificate(key), name='jojo-uninstall')
    try:
        erase(firestore.client(app), namespace())
    finally:
        firebase_admin.delete_app(app)
    print('Confirmed JoJo Firestore collections cleared.')

if __name__=='__main__':
    main()
