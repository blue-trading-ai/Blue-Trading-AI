from __future__ import annotations

import os
import secrets
import sys
from typing import Any

import requests
from sqlalchemy import inspect

from app.database.connection import SessionLocal, engine
from app.models.role_permission import (
    Permission,
    Role,
    UserRole,
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_OWNER,
    ROLE_USER,
)
from app.models.user import User
from app.services.role_permission_service import (
    OwnerRoleProtectionError,
    assign_role_to_user,
    ensure_default_user_role,
    ensure_owner_role,
    get_access_snapshot,
    get_user_permission_codes,
    get_user_role_names,
    revoke_role_from_user,
    seed_default_roles_and_permissions,
)


BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

OWNER_EMAIL = os.getenv(
    "OWNER_EMAIL",
    "bluetradingai06@gmail.com",
).strip().lower()

TIMEOUT = 20


class ValidationFailure(Exception):
    pass


def print_step(number: int, title: str) -> None:
    print(f"\n[{number}/10] {title}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationFailure(message)


def json_body(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise ValidationFailure(
            f"Response was not JSON: {response.text[:500]}"
        ) from exc

    require(
        isinstance(payload, dict),
        "Expected a JSON object response.",
    )

    return payload


def get_or_create_owner(db) -> User:
    owner = (
        db.query(User)
        .filter(User.email == OWNER_EMAIL)
        .first()
    )

    require(
        owner is not None,
        (
            "Owner account was not found. Register the owner "
            "account before running Version 41 tests."
        ),
    )

    return owner


def create_test_user(db) -> User:
    suffix = secrets.token_hex(5)
    email = f"v41.role.{suffix}@example.com"
    username = f"v41role_{suffix}"

    user = User(
        username=username,
        email=email,
        hashed_password="test-only-not-used",
        is_active=True,
        account_status="APPROVED",
    )

    if hasattr(user, "is_email_verified"):
        user.is_email_verified = True

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def cleanup_test_user(db, user_id: int) -> None:
    user = (
        db.query(User)
        .filter(User.id == int(user_id))
        .first()
    )

    if user is not None:
        db.delete(user)
        db.commit()


def main() -> int:
    print("=" * 68)
    print("BLUE TRADING AI - VERSION 41 ROLES & PERMISSIONS TEST")
    print("=" * 68)

    test_user_id: int | None = None

    try:
        print_step(1, "API reports Version 41")

        response = requests.get(
            f"{BASE_URL}/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Main API failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        payload = json_body(response)

        require(
            str(payload.get("version")) == "41.0.0",
            f"Expected version 41.0.0, got {payload}",
        )

        print("PASSED")

        print_step(2, "Role API is registered")

        response = requests.get(
            f"{BASE_URL}/roles/",
            timeout=TIMEOUT,
        )

        require(
            response.status_code == 200,
            (
                "Role API failed: "
                f"{response.status_code} {response.text}"
            ),
        )

        role_home = json_body(response)

        require(
            int(role_home.get("role_api_version", 0)) == 41,
            f"Expected role_api_version 41, got {role_home}",
        )

        print("PASSED")

        print_step(3, "Database contains Version 41 tables")

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        for table_name in {
            "roles",
            "permissions",
            "role_permissions",
            "user_roles",
        }:
            require(
                table_name in tables,
                f"Missing table: {table_name}",
            )

        print("PASSED")

        db = SessionLocal()

        try:
            print_step(4, "Default roles and permissions are seeded")

            result = seed_default_roles_and_permissions(
                db,
                commit=True,
            )

            role_names = {
                row.name
                for row in db.query(Role).all()
            }

            for role_name in {
                ROLE_OWNER,
                ROLE_ADMIN,
                ROLE_ANALYST,
                ROLE_USER,
            }:
                require(
                    role_name in role_names,
                    f"Missing seeded role: {role_name}",
                )

            permission_count = db.query(Permission).count()

            require(
                permission_count >= 11,
                (
                    "Expected at least 11 permissions, got "
                    f"{permission_count}"
                ),
            )

            print("PASSED")

            print_step(5, "Owner receives protected OWNER role")

            owner = get_or_create_owner(db)

            ensure_owner_role(
                db,
                user_id=int(owner.id),
                commit=True,
            )

            owner_snapshot = get_access_snapshot(
                db,
                user_id=int(owner.id),
            )

            require(
                ROLE_OWNER in owner_snapshot.roles,
                "Owner role was not assigned.",
            )
            require(
                owner_snapshot.is_owner is True,
                "Owner access snapshot is not marked owner.",
            )

            print("PASSED")

            print_step(6, "Standard USER role assignment works")

            test_user = create_test_user(db)
            test_user_id = int(test_user.id)

            assignment = ensure_default_user_role(
                db,
                user_id=test_user_id,
                assigned_by_user_id=int(owner.id),
                commit=True,
            )

            require(
                assignment.is_active is True,
                "USER role assignment is inactive.",
            )

            roles = get_user_role_names(
                db,
                user_id=test_user_id,
            )

            require(
                ROLE_USER in roles,
                "USER role was not assigned.",
            )

            print("PASSED")

            print_step(7, "USER permission inheritance works")

            permissions = get_user_permission_codes(
                db,
                user_id=test_user_id,
            )

            require(
                "signal:read" in permissions,
                "USER role is missing signal:read.",
            )
            require(
                "system:read" in permissions,
                "USER role is missing system:read.",
            )
            require(
                "role:assign" not in permissions,
                "USER role incorrectly has role:assign.",
            )

            print("PASSED")

            print_step(8, "ANALYST assignment expands permissions")

            assign_role_to_user(
                db,
                user_id=test_user_id,
                role_name=ROLE_ANALYST,
                assigned_by_user_id=int(owner.id),
                commit=True,
            )

            analyst_snapshot = get_access_snapshot(
                db,
                user_id=test_user_id,
            )

            require(
                ROLE_ANALYST in analyst_snapshot.roles,
                "ANALYST role was not assigned.",
            )
            require(
                "signal:create"
                in analyst_snapshot.permissions,
                "ANALYST role is missing signal:create.",
            )

            print("PASSED")

            print_step(9, "Role revocation removes inherited access")

            revoke_role_from_user(
                db,
                user_id=test_user_id,
                role_name=ROLE_ANALYST,
                reason="VERSION_41_TEST",
                commit=True,
            )

            revoked_snapshot = get_access_snapshot(
                db,
                user_id=test_user_id,
            )

            require(
                ROLE_ANALYST not in revoked_snapshot.roles,
                "ANALYST role remained active after revocation.",
            )
            require(
                "signal:create"
                not in revoked_snapshot.permissions,
                (
                    "Revoked ANALYST permission signal:create "
                    "is still active."
                ),
            )

            print("PASSED")

            print_step(10, "Owner role protection blocks normal assignment")

            blocked = False

            try:
                assign_role_to_user(
                    db,
                    user_id=test_user_id,
                    role_name=ROLE_OWNER,
                    assigned_by_user_id=int(owner.id),
                    allow_owner_role=False,
                    commit=True,
                )
            except OwnerRoleProtectionError:
                blocked = True

            require(
                blocked,
                "Protected OWNER role assignment was not blocked.",
            )

            active_owner_assignment = (
                db.query(UserRole)
                .join(Role, UserRole.role_id == Role.id)
                .filter(
                    UserRole.user_id == test_user_id,
                    Role.name == ROLE_OWNER,
                    UserRole.is_active.is_(True),
                )
                .first()
            )

            require(
                active_owner_assignment is None,
                "Test user incorrectly received OWNER role.",
            )

            print("PASSED")

        finally:
            if test_user_id is not None:
                cleanup_test_user(db, test_user_id)

            db.close()

        print("\n" + "=" * 68)
        print("VERSION 41 ROLES & PERMISSIONS TEST: 10/10 PASSED")
        print("=" * 68)
        return 0

    except requests.RequestException as exc:
        print(f"\nFAILED: API connection error: {exc}")
        return 1
    except ValidationFailure as exc:
        print(f"\nFAILED: {exc}")
        return 1
    except Exception as exc:
        print(
            "\nFAILED: Unexpected error: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

