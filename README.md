# Sistema de Inventario para pequeños negocios

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask)
![MySQL](https://img.shields.io/badge/MySQL-8-4479A1?logo=mysql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)

Aplicación web para controlar el inventario de bodegas, ferreterías y minimarkets: productos,
entradas y salidas de stock, alertas de reposición, kardex por producto, dashboard y reportes
en Excel y PDF. Construida con **Flask + MySQL** siguiendo una arquitectura por capas, con
transacciones seguras ante concurrencia y una suite de tests automatizados.

**Demo en vivo:** `https://<tu-servicio>.onrender.com` &nbsp;·&nbsp; usuario `admin` / `Admin123` o `empleado` / `Empleado123`
> La demo usa el plan gratuito: si estuvo inactiva, el primer acceso puede tardar cerca de un minuto en despertar.

---

## Capturas





Ejemplos de reportes generados por la aplicación: [inventario.pdf](docs/samples/inventario.pdf) ·
[inventario.xlsx](docs/samples/inventario.xlsx) · [movimientos.pdf](docs/samples/movimientos.pdf) ·
[movimientos.xlsx](docs/samples/movimientos.xlsx)

## Funcionalidades

- **Autenticación y roles.** Login con contraseñas hasheadas (scrypt). Roles *Administrador* y *Empleado*: el empleado no gestiona usuarios, no desactiva productos, no elimina catálogos ni registra ajustes.
- **Productos.** CRUD con SKU único, categoría, proveedor, precios, unidad de medida (enteras o fraccionables como kg y metros), stock mínimo, búsqueda, filtros, orden y paginación. Borrado lógico: se desactivan y conservan su historial.
- **Categorías y proveedores.** CRUD con validación del **RUC peruano** (dígito verificador de la SUNAT) e integridad referencial.
- **Movimientos de inventario.** Entradas (compra, devolución, ajuste) y salidas (venta, merma, devolución a proveedor, ajuste), con fecha, usuario responsable y observaciones. El stock se actualiza en una transacción con bloqueo de fila; **nunca queda negativo**.
- **Kardex por producto**, filtrable por fechas, con saldo inicial, entradas, salidas, costos y saldo final (con autoverificación).
- **Alertas de reposición** en la tabla de productos y en el dashboard.
- **Dashboard** con indicadores, lista "Por reponer", últimos movimientos y gráfico de entradas vs. salidas de 30 días (Chart.js).
- **Reportes** de inventario actual y de movimientos por rango de fechas, en **Excel** (con fórmulas vivas) y **PDF**.

## Tecnologías

| Capa | Herramientas |
|---|---|
| Backend | Python 3.11+, Flask 3 (Application Factory + Blueprints) |
| Datos | MySQL 8, SQLAlchemy 2.0 (ORM), Flask-Migrate (Alembic), PyMySQL |
| Seguridad | Flask-Login, Werkzeug (scrypt), Flask-WTF (CSRF) |
| Frontend | Jinja2, Bootstrap 5.3, Bootstrap Icons, Chart.js 4 |
| Reportes | openpyxl (Excel), ReportLab (PDF) |
| Calidad | pytest (modelos, servicios, rutas, permisos y reportes), configuración por variables de entorno |
| Despliegue | Gunicorn, Render + Aiven MySQL, o PythonAnywhere |

## Arquitectura

```mermaid
flowchart LR
    B[Navegador<br/>Jinja2 + Bootstrap + Chart.js] -->|HTTP + token CSRF| R[Rutas<br/>Blueprints]
    R --> F[Formularios<br/>Flask-WTF]
    R --> S[Servicios<br/>reglas de negocio]
    S --> M[Modelos<br/>SQLAlchemy]
    M --> DB[(MySQL 8)]
    S --> X[Exportadores<br/>Excel / PDF]
```

Las rutas solo reciben la petición, validan el formulario y llaman a un **servicio**. Toda regla de
negocio vive en `app/services/`. Por eso se prueba sin HTTP y se podría reutilizar en una API.

## Modelo de datos

```mermaid
erDiagram
    CATEGORIES ||--o{ PRODUCTS : clasifica
    SUPPLIERS |o--o{ PRODUCTS : provee
    PRODUCTS ||--o{ STOCK_MOVEMENTS : registra
    USERS ||--o{ STOCK_MOVEMENTS : realiza
    PRODUCTS {
        int id PK
        varchar sku UK
        varchar name
        decimal purchase_price
        decimal sale_price
        varchar unit
        decimal stock
        decimal min_stock
        bool is_active
    }
    STOCK_MOVEMENTS {
        int id PK
        int product_id FK
        int user_id FK
        enum movement_type
        enum reason
        decimal quantity
        decimal unit_cost
        decimal stock_before
        decimal stock_after
        datetime movement_date
    }
```

El DDL completo está en [`database/schema.sql`](database/schema.sql).

## Decisiones técnicas destacadas

- **Un único punto de cambio de stock.** `stock_service.register_movement()` bloquea la fila del producto (`SELECT ... FOR UPDATE`), valida contra el stock recién leído, inserta el movimiento y actualiza el stock **en una sola transacción**. Un test con dos hilos sobre MySQL comprueba que dos ventas simultáneas de la última unidad no se aprueban ambas.
- **Ledger inmutable y cronológico.** Los movimientos no se editan ni se borran: los errores se corrigen con ajustes. Cada movimiento guarda `stock_before` y `stock_after`, y no se permiten fechas futuras ni anteriores al último movimiento del producto. Así el kardex siempre cuadra.
- **Defensa en profundidad.** Las reglas se validan en el formulario, en el servicio y en la base de datos (`CHECK stock >= 0`, claves foráneas `RESTRICT`).
- **Dinero y cantidades en `DECIMAL`**, nunca en `FLOAT`. Los decimales de más se rechazan en vez de redondearse en silencio.
- **Zona horaria.** Las fechas se guardan en UTC y se muestran y filtran por día de Lima.
- **Seguridad web.** CSRF en todos los formularios, logout por POST, protección contra *open redirect* y mensajes de login que no revelan qué usuarios existen. Desactivar una cuenta cierra sus sesiones al instante.
- **Excel con fórmulas vivas.** Totales, valores y estados se recalculan si se edita el archivo. Los exportadores no dependen de la base de datos, así que se prueban de forma aislada.

## Instalación local

**Requisitos:** Python 3.11 o superior, MySQL 8 y Git.

```bash
# 1. Clonar el repositorio y crear un entorno virtual
git clone https://github.com/x949835964-a11y/inventory-system.git
cd inventory-system
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Crear la base de datos (edita antes la contraseña del script)
mysql -u root -p < database/create_database.sql

# 3. Configurar variables de entorno
cp .env.example .env              # Windows: copy .env.example .env
# Edita .env: SECRET_KEY y DATABASE_URL

# 4. Crear las tablas y cargar los datos demo
flask db upgrade
flask seed

# 5. Ejecutar
flask run                         # http://127.0.0.1:5000
```

Para empezar sin datos demo, usa `flask create-admin` en lugar de `flask seed`.

### Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `SECRET_KEY` | Sí | Clave para firmar sesiones. Genérala con `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Sí | `mysql+pymysql://usuario:clave@host:3306/base?charset=utf8mb4` |
| `APP_ENV` | No | `development` (por defecto) o `production` |
| `BUSINESS_NAME` | No | Nombre del negocio que aparece en los reportes |
| `DEMO_MODE` | No | `true` muestra las credenciales demo en el login y protege esas cuentas |
| `DATABASE_SSL_CA` | No | Ruta al certificado CA si el MySQL exige TLS (por ejemplo, Aiven) |
| `APP_TIMEZONE` | No | Zona horaria para mostrar fechas (por defecto, `America/Lima`) |

## Usuarios demo

Se crean con `flask seed`:

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin` | `Admin123` |
| Empleado | `empleado` | `Empleado123` |

`flask seed` también crea 8 categorías, 7 proveedores (con RUC válido), 30 productos y unos 45 días de movimientos simulados. Algunos productos quedan en alerta para que el dashboard tenga datos que mostrar. Para volver a cargar la demo desde cero: `flask seed --reset`.

## Tests

```bash
pytest                    # usa SQLite en memoria: rápido y sin instalar nada más
```

El test de concurrencia necesita MySQL real, porque SQLite no implementa `FOR UPDATE`. Para correrlo, apunta `TEST_DATABASE_URL` a una base **separada y desechable**:

```bash
TEST_DATABASE_URL="mysql+pymysql://usuario:clave@localhost:3306/inventory_test?charset=utf8mb4" pytest
```

## Estructura del proyecto

```
inventory-system/
├── app/
│   ├── __init__.py          # create_app(): factory, extensiones, blueprints
│   ├── config.py            # configuración por entorno (variables .env)
│   ├── extensions.py        # db, migrate, login_manager, csrf
│   ├── cli.py               # flask create-admin, flask seed
│   ├── seed.py              # generador de datos demo
│   ├── models/              # User, Category, Supplier, Product, StockMovement
│   ├── services/            # reglas de negocio (stock, kardex, reportes...)
│   │   └── exporters/       # Excel (openpyxl) y PDF (ReportLab)
│   ├── routes/              # blueprints: auth, products, movements, reports...
│   ├── forms/               # formularios Flask-WTF
│   ├── utils/               # fechas, formatos, seguridad, RUC
│   ├── templates/           # Jinja2 + Bootstrap 5
│   └── static/              # CSS y JavaScript (dashboard con Chart.js)
├── migrations/              # migraciones de Flask-Migrate
├── database/                # create_database.sql, schema.sql
├── docs/                    # guía de despliegue, capturas y reportes de ejemplo
├── tests/                   # pytest
├── render.yaml              # despliegue en Render (Blueprint)
├── requirements.txt
└── run.py                   # punto de entrada WSGI
```

## Despliegue

La guía paso a paso para publicar una demo gratuita está en [`docs/DEPLOY.md`](docs/DEPLOY.md).
Incluye dos opciones: Render + Aiven (MySQL gratis) y PythonAnywhere.

## Mejoras futuras

- Valorización por costo promedio ponderado.
- Límite de intentos de login (Flask-Limiter) e invalidación de sesiones al cambiar la contraseña.
- API REST para integrar un punto de venta, reutilizando la capa de servicios.
- Códigos de barras para registrar ventas con lector.
- Soporte para varios almacenes o sucursales.

## Autor

**Diego Edson Gamonal Paucar**, estudiante de Ingeniería de Sistemas en la Universidad Autónoma del Perú.

[LinkedIn](https://www.linkedin.com/in/edson-diego-gamonal-paucar-567260426) · [GitHub](https://github.com/x949835964-a11y)
