"""Run interactively inside the deployed App Service after DB identity bootstrap.

No passwords are accepted on command lines, written to files, or logged.
"""
import getpass
import os
from . import db as m
from .seed import seed

def main():
    if os.getenv("APP_ENV") != "production":
        raise SystemExit("Use manage.py init/reset for local demo initialization")
    passwords={}
    for role in ("author","reviewer","releaser"):
        value=getpass.getpass(f"Set {role} password (16+ characters): ")
        if len(value)<16 or value in passwords.values() or value=="LabelTrace-demo-2026!":
            raise SystemExit("Use distinct strong passwords; documented local demo password is not allowed")
        if getpass.getpass(f"Confirm {role} password: ")!=value:
            raise SystemExit("Password confirmation does not match")
        passwords[role]=value
    with m.transaction() as db:
        if m.rows(db,m.User) or m.rows(db,m.Product):
            raise SystemExit("Database already initialized; accounts/history were not overwritten")
        seed(db,passwords)
    print("Synthetic family and three role accounts initialized. Passwords were not logged.")

if __name__=='__main__':
    main()
