-- Admin bootstrap SQL (SQLite/PostgreSQL compatible syntax where possible)
-- Creates/updates a platform admin user and grants platform_admin role.
--
-- Strong default password (change immediately after first login):
--   AudeLA_Admin#2026!X9qP7vT2$Lm
-- Hash generated with werkzeug.security.generate_password_hash()
--   scrypt:32768:8:1$oFTCfkAmol3cpc0K$85b6c415d0c19996b8758b5f6d2a82a6b66793d253fe7342b74a8b09478a2fa2a273057e229d09465bc9e3001a3bd6e2b5f24a48a1f2f98a40fccd2ec8068e76

BEGIN;

INSERT INTO tenants (slug, name, settings_json, plan, created_at)
VALUES ('platform-admin', 'Platform Admin', '{}', 'enterprise', CURRENT_TIMESTAMP)
ON CONFLICT(slug) DO NOTHING;

INSERT INTO roles (code, description)
VALUES ('platform_admin', 'Super administrateur plateforme')
ON CONFLICT(code) DO NOTHING;

INSERT INTO users (tenant_id, email, password_hash, status, created_at, last_login_at)
SELECT t.id,
       'admin_user',
       'scrypt:32768:8:1$oFTCfkAmol3cpc0K$85b6c415d0c19996b8758b5f6d2a82a6b66793d253fe7342b74a8b09478a2fa2a273057e229d09465bc9e3001a3bd6e2b5f24a48a1f2f98a40fccd2ec8068e76',
       'active',
       CURRENT_TIMESTAMP,
       NULL
FROM tenants t
WHERE t.slug = 'platform-admin'
ON CONFLICT(tenant_id, email) DO UPDATE
SET password_hash = EXCLUDED.password_hash,
    status = 'active';

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
JOIN tenants t ON t.id = u.tenant_id
JOIN roles r ON r.code = 'platform_admin'
WHERE t.slug = 'platform-admin'
  AND u.email = 'admin_user'
ON CONFLICT(user_id, role_id) DO NOTHING;

COMMIT;

-- Password rotation (manual):
-- 1) Generate a new hash with:
--    /home/testuser/audela_flask_website/.venv/bin/python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('NEW_VERY_STRONG_PASSWORD'))"
-- 2) Update hash with:
--    UPDATE users
--    SET password_hash = 'PASTE_NEW_HASH_HERE'
--    WHERE email = 'admin_user';
