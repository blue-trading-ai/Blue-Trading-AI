"""Version 41 roles and permissions

Revision ID: v41_roles_permissions
Revises: v39_account_security_tokens
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.orm import Session


revision: str = "v41_roles_permissions"
down_revision: Union[str, None] = "v39_account_security_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLE_TABLE = "roles"
PERMISSION_TABLE = "permissions"
ROLE_PERMISSION_TABLE = "role_permissions"
USER_ROLE_TABLE = "user_roles"


SYSTEM_PERMISSIONS = {
    "user:read": (
        "Read Users",
        "View user accounts and account status.",
    ),
    "user:approve": (
        "Approve Users",
        "Approve or reject pending user accounts.",
    ),
    "user:suspend": (
        "Suspend Users",
        "Suspend or restore user accounts.",
    ),
    "role:read": (
        "Read Roles",
        "View roles, permissions, and assignments.",
    ),
    "role:assign": (
        "Assign Roles",
        "Assign and revoke non-owner roles.",
    ),
    "audit:read": (
        "Read Security Audits",
        "View security audit events and access logs.",
    ),
    "signal:read": (
        "Read Signals",
        "View trading signals and signal history.",
    ),
    "signal:create": (
        "Create Signals",
        "Generate and store trading signals.",
    ),
    "signal:manage": (
        "Manage Signals",
        "Manage signal records and signal outcomes.",
    ),
    "system:read": (
        "Read System",
        "View backend health and system metadata.",
    ),
    "system:manage": (
        "Manage System",
        "Manage protected system settings.",
    ),
}


SYSTEM_ROLES = {
    "OWNER": (
        "Owner",
        "Full platform control. This role is reserved for the owner.",
        set(SYSTEM_PERMISSIONS),
    ),
    "ADMIN": (
        "Administrator",
        "Manage users, audits, roles, and trading records without owner-only system control.",
        {
            "user:read",
            "user:approve",
            "user:suspend",
            "role:read",
            "role:assign",
            "audit:read",
            "signal:read",
            "signal:create",
            "signal:manage",
            "system:read",
        },
    ),
    "ANALYST": (
        "Analyst",
        "View and create trading analysis and signals.",
        {
            "signal:read",
            "signal:create",
            "system:read",
        },
    ),
    "USER": (
        "User",
        "Standard approved user access.",
        {
            "signal:read",
            "system:read",
        },
    ),
}


def _table_exists(table_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())

    if table_name not in inspector.get_table_names():
        return set()

    return {
        str(item.get("name"))
        for item in inspector.get_indexes(table_name)
        if item.get("name")
    }


def _create_roles_table() -> None:
    if not _table_exists(ROLE_TABLE):
        op.create_table(
            ROLE_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "name",
                sa.String(length=40),
                nullable=False,
            ),
            sa.Column(
                "display_name",
                sa.String(length=100),
                nullable=False,
            ),
            sa.Column(
                "description",
                sa.String(length=500),
                nullable=True,
            ),
            sa.Column(
                "is_system",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "name",
                name="uq_roles_name",
            ),
        )

    existing = _index_names(ROLE_TABLE)

    expected = {
        "ix_roles_id": ["id"],
        "ix_roles_name": ["name"],
        "ix_roles_is_system": ["is_system"],
        "ix_roles_is_active": ["is_active"],
    }

    for name, columns in expected.items():
        if name not in existing:
            op.create_index(
                name,
                ROLE_TABLE,
                columns,
                unique=False,
            )


def _create_permissions_table() -> None:
    if not _table_exists(PERMISSION_TABLE):
        op.create_table(
            PERMISSION_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "code",
                sa.String(length=100),
                nullable=False,
            ),
            sa.Column(
                "display_name",
                sa.String(length=150),
                nullable=False,
            ),
            sa.Column(
                "description",
                sa.String(length=500),
                nullable=True,
            ),
            sa.Column(
                "is_system",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "code",
                name="uq_permissions_code",
            ),
        )

    existing = _index_names(PERMISSION_TABLE)

    expected = {
        "ix_permissions_id": ["id"],
        "ix_permissions_code": ["code"],
        "ix_permissions_is_system": ["is_system"],
        "ix_permissions_is_active": ["is_active"],
    }

    for name, columns in expected.items():
        if name not in existing:
            op.create_index(
                name,
                PERMISSION_TABLE,
                columns,
                unique=False,
            )


def _create_role_permissions_table() -> None:
    if not _table_exists(ROLE_PERMISSION_TABLE):
        op.create_table(
            ROLE_PERMISSION_TABLE,
            sa.Column(
                "role_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "permission_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(
                ["role_id"],
                ["roles.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["permission_id"],
                ["permissions.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint(
                "role_id",
                "permission_id",
            ),
        )

    existing = _index_names(ROLE_PERMISSION_TABLE)

    if (
        "ix_role_permissions_role_permission"
        not in existing
    ):
        op.create_index(
            "ix_role_permissions_role_permission",
            ROLE_PERMISSION_TABLE,
            ["role_id", "permission_id"],
            unique=True,
        )


def _create_user_roles_table() -> None:
    if not _table_exists(USER_ROLE_TABLE):
        op.create_table(
            USER_ROLE_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "role_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "assigned_by_user_id",
                sa.Integer(),
                nullable=True,
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "assigned_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "revoked_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "revoke_reason",
                sa.String(length=200),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["role_id"],
                ["roles.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["assigned_by_user_id"],
                ["users.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "role_id",
                name="uq_user_roles_user_role",
            ),
        )

    existing = _index_names(USER_ROLE_TABLE)

    expected = {
        "ix_user_roles_id": ["id"],
        "ix_user_roles_user_id": ["user_id"],
        "ix_user_roles_role_id": ["role_id"],
        "ix_user_roles_assigned_by_user_id": [
            "assigned_by_user_id"
        ],
        "ix_user_roles_is_active": ["is_active"],
        "ix_user_roles_user_active": [
            "user_id",
            "is_active",
        ],
        "ix_user_roles_role_active": [
            "role_id",
            "is_active",
        ],
    }

    for name, columns in expected.items():
        if name not in existing:
            op.create_index(
                name,
                USER_ROLE_TABLE,
                columns,
                unique=False,
            )


def _seed_defaults() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        permission_ids: dict[str, int] = {}

        for code, metadata in SYSTEM_PERMISSIONS.items():
            row = session.execute(
                sa.text(
                    """
                    SELECT id
                    FROM permissions
                    WHERE code = :code
                    """
                ),
                {"code": code},
            ).first()

            if row is None:
                session.execute(
                    sa.text(
                        """
                        INSERT INTO permissions (
                            code,
                            display_name,
                            description,
                            is_system,
                            is_active,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            :code,
                            :display_name,
                            :description,
                            1,
                            1,
                            CURRENT_TIMESTAMP,
                            CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {
                        "code": code,
                        "display_name": metadata[0],
                        "description": metadata[1],
                    },
                )
            else:
                session.execute(
                    sa.text(
                        """
                        UPDATE permissions
                        SET
                            display_name = :display_name,
                            description = :description,
                            is_system = 1,
                            is_active = 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE code = :code
                        """
                    ),
                    {
                        "code": code,
                        "display_name": metadata[0],
                        "description": metadata[1],
                    },
                )

            permission_id = session.execute(
                sa.text(
                    """
                    SELECT id
                    FROM permissions
                    WHERE code = :code
                    """
                ),
                {"code": code},
            ).scalar_one()

            permission_ids[code] = int(permission_id)

        for role_name, metadata in SYSTEM_ROLES.items():
            display_name, description, permission_codes = (
                metadata
            )

            row = session.execute(
                sa.text(
                    """
                    SELECT id
                    FROM roles
                    WHERE name = :name
                    """
                ),
                {"name": role_name},
            ).first()

            if row is None:
                session.execute(
                    sa.text(
                        """
                        INSERT INTO roles (
                            name,
                            display_name,
                            description,
                            is_system,
                            is_active,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            :name,
                            :display_name,
                            :description,
                            1,
                            1,
                            CURRENT_TIMESTAMP,
                            CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {
                        "name": role_name,
                        "display_name": display_name,
                        "description": description,
                    },
                )
            else:
                session.execute(
                    sa.text(
                        """
                        UPDATE roles
                        SET
                            display_name = :display_name,
                            description = :description,
                            is_system = 1,
                            is_active = 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE name = :name
                        """
                    ),
                    {
                        "name": role_name,
                        "display_name": display_name,
                        "description": description,
                    },
                )

            role_id = session.execute(
                sa.text(
                    """
                    SELECT id
                    FROM roles
                    WHERE name = :name
                    """
                ),
                {"name": role_name},
            ).scalar_one()

            session.execute(
                sa.text(
                    """
                    DELETE FROM role_permissions
                    WHERE role_id = :role_id
                    """
                ),
                {"role_id": int(role_id)},
            )

            for code in sorted(permission_codes):
                session.execute(
                    sa.text(
                        """
                        INSERT INTO role_permissions (
                            role_id,
                            permission_id,
                            created_at
                        )
                        VALUES (
                            :role_id,
                            :permission_id,
                            CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {
                        "role_id": int(role_id),
                        "permission_id": permission_ids[code],
                    },
                )

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def upgrade() -> None:
    _create_roles_table()
    _create_permissions_table()
    _create_role_permissions_table()
    _create_user_roles_table()
    _seed_defaults()


def downgrade() -> None:
    for table_name in (
        USER_ROLE_TABLE,
        ROLE_PERMISSION_TABLE,
        PERMISSION_TABLE,
        ROLE_TABLE,
    ):
        if _table_exists(table_name):
            op.drop_table(table_name)