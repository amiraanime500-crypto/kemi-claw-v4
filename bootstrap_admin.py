"""Create the first admin account. Run once after deployment."""
import sys

from kemi_claw.auth.models import Role
from kemi_claw.auth.security import hash_password
from kemi_claw.auth.store import UserStore


if __name__ == "__main__":
    username, password = sys.argv[1], sys.argv[2]
    store = UserStore()
    if store.get(username):
        print("user already exists")
        sys.exit(1)
    store.create(username, hash_password(password), Role.ADMIN)
    print(f"admin '{username}' created")
