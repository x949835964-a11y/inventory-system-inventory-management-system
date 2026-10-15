-- Run once as MySQL root to create the database and a dedicated app user.
-- Then put the same credentials in DATABASE_URL inside your .env file.
-- The tables are created afterwards by Flask-Migrate (`flask db upgrade`).

CREATE DATABASE IF NOT EXISTS inventory_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Change the password before running this script.
CREATE USER IF NOT EXISTS 'inventory_user'@'localhost' IDENTIFIED BY 'change_this_password';

-- Least privilege: the app user only has rights on its own database.
GRANT ALL PRIVILEGES ON inventory_db.* TO 'inventory_user'@'localhost';
FLUSH PRIVILEGES;
