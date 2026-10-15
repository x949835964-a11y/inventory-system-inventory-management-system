-- Reference DDL (MySQL 8.0.16+) equivalent to the SQLAlchemy models.
-- The source of truth is the models + Flask-Migrate migrations; use this file
-- to read the schema or to create it manually in MySQL Workbench without Python.
-- Do NOT run it and `flask db upgrade` on the same database.

USE inventory_db;

CREATE TABLE users (
    id              INT          NOT NULL AUTO_INCREMENT,
    username        VARCHAR(50)  NOT NULL,
    full_name       VARCHAR(120) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            ENUM('admin', 'employee') NOT NULL,
    is_active       BOOL         NOT NULL,
    last_login_at   DATETIME     NULL,
    created_at      DATETIME     NOT NULL,
    updated_at      DATETIME     NOT NULL,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_username UNIQUE (username)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE categories (
    id              INT          NOT NULL AUTO_INCREMENT,
    name            VARCHAR(80)  NOT NULL,
    description     VARCHAR(255) NULL,
    created_at      DATETIME     NOT NULL,
    updated_at      DATETIME     NOT NULL,
    CONSTRAINT pk_categories PRIMARY KEY (id),
    CONSTRAINT uq_categories_name UNIQUE (name)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE suppliers (
    id              INT          NOT NULL AUTO_INCREMENT,
    name            VARCHAR(120) NOT NULL,
    ruc             VARCHAR(11)  NULL,
    phone           VARCHAR(20)  NULL,
    email           VARCHAR(120) NULL,
    address         VARCHAR(255) NULL,
    contact_name    VARCHAR(120) NULL,
    is_active       BOOL         NOT NULL,
    created_at      DATETIME     NOT NULL,
    updated_at      DATETIME     NOT NULL,
    CONSTRAINT pk_suppliers PRIMARY KEY (id),
    CONSTRAINT uq_suppliers_ruc UNIQUE (ruc),
    INDEX ix_suppliers_name (name)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE products (
    id              INT            NOT NULL AUTO_INCREMENT,
    sku             VARCHAR(40)    NOT NULL,
    name            VARCHAR(150)   NOT NULL,
    description     TEXT           NULL,
    category_id     INT            NOT NULL,
    supplier_id     INT            NULL,
    purchase_price  DECIMAL(10, 2) NOT NULL,
    sale_price      DECIMAL(10, 2) NOT NULL,
    unit            VARCHAR(10)    NOT NULL,
    stock           DECIMAL(12, 3) NOT NULL DEFAULT 0,
    min_stock       DECIMAL(12, 3) NOT NULL DEFAULT 0,
    is_active       BOOL           NOT NULL,
    created_at      DATETIME       NOT NULL,
    updated_at      DATETIME       NOT NULL,
    CONSTRAINT pk_products PRIMARY KEY (id),
    CONSTRAINT uq_products_sku UNIQUE (sku),
    CONSTRAINT fk_products_category_id_categories
        FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE RESTRICT,
    CONSTRAINT fk_products_supplier_id_suppliers
        FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE RESTRICT,
    CONSTRAINT ck_products_stock_non_negative          CHECK (stock >= 0),
    CONSTRAINT ck_products_min_stock_non_negative      CHECK (min_stock >= 0),
    CONSTRAINT ck_products_purchase_price_non_negative CHECK (purchase_price >= 0),
    CONSTRAINT ck_products_sale_price_non_negative     CHECK (sale_price >= 0),
    INDEX ix_products_name (name),
    INDEX ix_products_category_id (category_id),
    INDEX ix_products_supplier_id (supplier_id),
    INDEX ix_products_is_active (is_active)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE stock_movements (
    id              INT            NOT NULL AUTO_INCREMENT,
    product_id      INT            NOT NULL,
    user_id         INT            NOT NULL,
    movement_type   ENUM('in', 'out') NOT NULL,
    reason          ENUM('purchase', 'customer_return', 'sale', 'shrinkage',
                         'supplier_return', 'adjustment') NOT NULL,
    quantity        DECIMAL(12, 3) NOT NULL,
    unit_cost       DECIMAL(10, 2) NOT NULL,
    stock_before    DECIMAL(12, 3) NOT NULL,
    stock_after     DECIMAL(12, 3) NOT NULL,
    movement_date   DATETIME       NOT NULL,
    notes           TEXT           NULL,
    created_at      DATETIME       NOT NULL,
    CONSTRAINT pk_stock_movements PRIMARY KEY (id),
    CONSTRAINT fk_stock_movements_product_id_products
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_movements_user_id_users
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_stock_movements_quantity_positive        CHECK (quantity > 0),
    CONSTRAINT ck_stock_movements_stock_after_non_negative CHECK (stock_after >= 0),
    INDEX ix_stock_movements_product_date (product_id, movement_date),
    INDEX ix_stock_movements_user_id (user_id),
    INDEX ix_stock_movements_movement_date (movement_date)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
