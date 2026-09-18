"""Coordinate best-effort external effects with the database transaction.

Callbacks never change the authoritative transaction. Mail runs after commit;
newly written files are removed on rollback. Nested rollbacks discard only
callbacks registered inside that savepoint.
"""
from flask import current_app
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.extensions import db


def _register(kind, callback):
    session = db.session()
    if not session.in_transaction():
        session.begin()
    transaction = session.get_nested_transaction() or session.get_transaction()
    session.info.setdefault('transaction_effects', []).append((transaction, kind, callback))


def after_commit(callback):
    _register('commit', callback)


def on_rollback(callback):
    _register('rollback', callback)


def _belongs_to(transaction, ancestor):
    while transaction is not None:
        if transaction is ancestor:
            return True
        transaction = transaction.parent
    return False


@event.listens_for(Session, 'after_commit')
def _committed(session):
    if session.in_nested_transaction():
        return
    effects = session.info.pop('transaction_effects', [])
    for _, kind, callback in effects:
        if kind == 'commit':
            callback()


@event.listens_for(Session, 'after_soft_rollback')
def _rolled_back(session, previous_transaction):
    remaining = []
    for transaction, kind, callback in session.info.pop('transaction_effects', []):
        if _belongs_to(transaction, previous_transaction):
            if kind == 'rollback':
                try:
                    callback()
                except OSError:
                    current_app.logger.exception('Could not remove uncommitted document file')
        else:
            remaining.append((transaction, kind, callback))
    if remaining:
        session.info['transaction_effects'] = remaining
