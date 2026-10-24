"""
seed.py - Creates the demo users. Run once:  python seed.py

  staff    -> username: staff1  password: Staff@123  (staff can ONLY be created here)
  customer -> username: demo    password: Demo@123

Safe to run again: existing users are skipped.
"""
import models  # noqa: F401
from auth import hash_password
from database import Base, SessionLocal, engine
from models import User

DEMO_USERS = [
    {"name": "Anita Staff", "username": "staff1", "password": "Staff@123", "role": "staff"},
    {"name": "Rahul Sharma", "username": "demo", "password": "Demo@123", "role": "customer"},
]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for u in DEMO_USERS:
            if db.query(User).filter(User.username == u["username"]).first():
                print(f"User '{u['username']}' already exists - skipped")
                continue
            db.add(User(name=u["name"], username=u["username"],
                        password_hash=hash_password(u["password"]), role=u["role"]))
            print(f"Created {u['role']} user '{u['username']}'")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
