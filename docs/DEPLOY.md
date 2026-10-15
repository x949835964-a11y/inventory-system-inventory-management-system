# Despliegue de una demo pública

> Condiciones verificadas en octubre de 2026. Los planes gratuitos cambian con frecuencia: confirma
> los límites actuales en la web de cada servicio antes de empezar.

## ¿Qué opción elegir?

| Opción | Costo | Base de datos | Ventajas | Límites |
|---|---|---|---|---|
| **A. Render + Aiven** (recomendada) | Gratis | MySQL 8 (Aiven) | Mismo motor que en desarrollo; despliegue automático desde GitHub | La app "duerme" tras 15 min sin visitas y tarda ~1 min en despertar |
| **B1. PythonAnywhere gratis** | Gratis | SQLite | Muy simple, sin tiempos de arranque | Sin MySQL en cuentas nuevas; la web app se desactiva si no la renuevas cada mes |
| **B2. PythonAnywhere Developer** | USD 10/mes | MySQL | Producción estable, sin dormir | De pago |

**Importante sobre PythonAnywhere:** desde enero de 2026, las cuentas gratuitas **nuevas** ya no incluyen
MySQL (solo lo conservan las cuentas creadas antes de esa fecha) y las web apps sin uso se desactivan al
mes. Por eso, para una demo con MySQL sin costo, la opción recomendada es Render + Aiven. Si tu cuenta de
PythonAnywhere es anterior a enero de 2026, sigue la opción B2: los pasos son los mismos.

### Antes de cualquier opción

1. Sube el proyecto a GitHub **con la carpeta `migrations/`** (la generaste en la Etapa 1).
2. Comprueba que `.env` **no** esté en el repositorio (`git status` no debe mostrarlo; está en `.gitignore`).
3. Corre `pytest` una última vez.

---

## Opción A: Render (aplicación) + Aiven (MySQL)

### A1. Crear la base de datos MySQL en Aiven

1. Crea una cuenta en [aiven.io](https://aiven.io). El plan gratuito no pide tarjeta.
2. **Create service → MySQL → plan Free.** Elige la región disponible más cercana.
3. Cuando el servicio esté *Running*, en **Overview → Connection information** anota: `Host`, `Port`, `User` (`avnadmin`), `Password` y `Database` (`defaultdb`).
4. Descarga el **CA certificate** (`ca.pem`) desde esa misma pantalla. Aiven exige conexiones cifradas (TLS).
5. Arma tu `DATABASE_URL`:

   ```
   mysql+pymysql://avnadmin:TU_PASSWORD@TU_HOST:TU_PUERTO/defaultdb?charset=utf8mb4
   ```

   Si la contraseña tiene caracteres como `@`, `/` o `#`, codifícalos en la URL (por ejemplo, `@` se escribe `%40`).

> Aiven puede apagar un servicio gratuito que no tiene actividad, y avisa antes por correo. Si se apaga,
> vuelve a encenderlo desde la consola. La demo mantiene la base activa mientras recibe visitas.

### A2. Crear las tablas y cargar la demo (desde tu computadora)

Render no ofrece consola en el plan gratuito. Por eso cargas los datos desde tu equipo, apuntando a Aiven.
Abre una terminal en la carpeta del proyecto, con el entorno virtual activado:

```bash
# Linux / Mac
export DATABASE_URL="mysql+pymysql://avnadmin:...@...:.../defaultdb?charset=utf8mb4"
export DATABASE_SSL_CA="/ruta/a/ca.pem"
flask db upgrade
flask seed
```

```powershell
# Windows PowerShell
$env:DATABASE_URL="mysql+pymysql://avnadmin:...@...:.../defaultdb?charset=utf8mb4"
$env:DATABASE_SSL_CA="C:\ruta\a\ca.pem"
flask db upgrade
flask seed
```

Las variables definidas en la terminal tienen prioridad sobre tu `.env` local, así que tu base de desarrollo no se toca.
Al terminar, `flask seed` muestra un resumen y los usuarios demo. Contra un servidor remoto, la carga de unos
2 300 movimientos puede tardar algunos minutos. Para acelerarla, usa `flask seed --days 20`.

### A3. Publicar la aplicación en Render

1. Crea una cuenta en [render.com](https://render.com) y conecta tu GitHub.
2. **New → Blueprint** y elige tu repositorio. Render lee `render.yaml` y propone el servicio `inventario-flask` en plan *Free*.
3. Cuando lo pida, pega tu `DATABASE_URL`. La `SECRET_KEY` se genera sola.
4. En el servicio, ve a **Environment → Secret Files** y agrega un archivo llamado `ca.pem` con el contenido del certificado de Aiven. Render lo deja disponible en `/etc/secrets/ca.pem`, que es la ruta que ya usa `DATABASE_SSL_CA` en `render.yaml`.
5. Despliega. Cada arranque ejecuta `flask db upgrade` (aplica migraciones nuevas), `flask seed --if-empty` (carga la demo solo si la base está vacía; nunca borra datos) y luego `gunicorn run:app`.
6. Abre `https://<tu-servicio>.onrender.com/health`. Debe responder `{"database": "ok", "status": "ok"}`.

**Si prefieres configurarlo a mano en lugar del Blueprint**, crea un *Web Service* con estos valores:

- Runtime: Python.
- Build command: `pip install -r requirements.txt`.
- Start command: `flask db upgrade && flask seed --if-empty --days 20 && gunicorn run:app --workers 2 --timeout 60`.
- Variables de entorno: `FLASK_APP=run.py`, `APP_ENV=production`, `DEMO_MODE=true`, `SECRET_KEY`, `DATABASE_URL` y `DATABASE_SSL_CA=/etc/secrets/ca.pem`.

La versión de Python se toma del archivo `.python-version` (3.12).

### A4. Mantener la demo

- **Primera visita lenta.** El servicio gratuito se duerme tras 15 minutos sin tráfico y tarda alrededor de un minuto en despertar. Avísalo en tu CV o README ("la demo puede tardar ~1 min en cargar").
- **Reiniciar los datos.** Si los visitantes dejan la demo desordenada, repite el paso A2 con `flask seed --reset`.
- **Actualizar la app.** Cada `git push` a la rama principal vuelve a desplegar automáticamente.

---

## Opción B: PythonAnywhere

### B1. Cuenta gratuita con SQLite

La aplicación usa SQLAlchemy, así que funciona igual con SQLite: solo cambia `DATABASE_URL`. Es suficiente
para una demo. Para producción real, usa MySQL.

1. Crea una cuenta *Beginner* en [pythonanywhere.com](https://www.pythonanywhere.com).
2. Abre una **Bash console** y ejecuta:

   ```bash
   git clone https://github.com/x949835964-a11y/inventory-system.git
   cd inventory-system
   mkvirtualenv --python=python3.12 inventario
   pip install -r requirements.txt
   ```

3. Crea el archivo `.env` con `nano .env`. Reemplaza `TU_USUARIO` por tu usuario de PythonAnywhere (son 4 barras después de `sqlite:`):

   ```
   FLASK_APP=run.py
   APP_ENV=production
   DEMO_MODE=true
   SECRET_KEY=pega-aqui-una-clave-larga-y-aleatoria
   DATABASE_URL=sqlite:////home/TU_USUARIO/inventory-system/inventario.db
   BUSINESS_NAME=Bodega Demo
   ```

4. Crea las tablas y carga la demo:

   ```bash
   flask db upgrade
   flask seed
   ```

5. En la pestaña **Web → Add a new web app → Manual configuration → Python 3.12**:
   - **Virtualenv:** `/home/TU_USUARIO/.virtualenvs/inventario`.
   - **Source code:** `/home/TU_USUARIO/inventory-system`.
   - **WSGI configuration file**: borra el contenido y deja:

     ```python
     import sys
     from pathlib import Path

     project = Path("/home/TU_USUARIO/inventory-system")
     sys.path.insert(0, str(project))

     from dotenv import load_dotenv
     load_dotenv(project / ".env")

     from run import app as application  # noqa: E402
     ```

   - **Static files:** URL `/static/` → directorio `/home/TU_USUARIO/inventory-system/app/static`.
6. Pulsa **Reload** y abre `https://TU_USUARIO.pythonanywhere.com/health`.
7. **Renueva la web app cada mes** con el botón para extenderla de la pestaña Web. Si no la renuevas, se desactiva.

### B2. Cuenta con MySQL (plan Developer, o cuentas anteriores a 2026)

Sigue los mismos pasos que en B1, con estos cambios:

1. En la pestaña **Databases**, define una contraseña de MySQL y crea la base `inventario`. Su nombre completo será `TU_USUARIO$inventario`.
2. Usa esta `DATABASE_URL` en `.env`. En la URL, el `$` va codificado como `%24`:

   ```
   DATABASE_URL=mysql+pymysql://TU_USUARIO:TU_PASSWORD_MYSQL@TU_USUARIO.mysql.pythonanywhere-services.com/TU_USUARIO%24inventario?charset=utf8mb4
   ```

   El *host* exacto aparece en la pestaña Databases: cópialo de allí.
3. La app ya usa `pool_recycle=280`, que es lo que PythonAnywhere recomienda porque cierra las conexiones MySQL inactivas a los 300 segundos.

---

## Checklist después de publicar

- [ ] `/health` responde `"database": "ok"`.
- [ ] El login muestra el recuadro con las cuentas demo (`DEMO_MODE=true`).
- [ ] Entras como `empleado` y no ves "Usuarios"; `/users/` devuelve 403.
- [ ] Registras una venta y el stock baja; con más cantidad que el stock, aparece "Stock insuficiente".
- [ ] El dashboard muestra el gráfico; los reportes Excel y PDF se descargan.
- [ ] Las cuentas demo no permiten cambiar la contraseña (mensaje de "demo pública").
- [ ] Agregas el enlace de la demo al README, a tu CV y a LinkedIn.

## Problemas frecuentes

| Síntoma | Causa probable y solución |
|---|---|
| `Missing environment variables: SECRET_KEY` | Falta la variable en Render, o falta el `.env` / `load_dotenv` en el archivo WSGI de PythonAnywhere. |
| `Access denied for user` | Usuario o contraseña incorrectos en `DATABASE_URL`, o hay caracteres especiales sin codificar (`@` → `%40`, `$` → `%24`). |
| Error SSL o `Connections using insecure transport are prohibited` | Falta `DATABASE_SSL_CA`, o el Secret File `ca.pem` no está cargado en Render. |
| `Lost connection to MySQL server` | Conexiones inactivas cerradas por el servidor. Ya está mitigado con `pool_pre_ping` y `pool_recycle`; si persiste, revisa que el servicio de base de datos esté encendido. |
| La página carga sin estilos en PythonAnywhere | Falta el mapeo de archivos estáticos `/static/` en la pestaña Web. |
| `flask: command not found` en Render | Revisa que el build haya instalado `requirements.txt` y que exista `FLASK_APP=run.py`. |

## Referencias

- PythonAnywhere: [funciones de las cuentas gratuitas](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/), [tipos de bases de datos](https://help.pythonanywhere.com/pages/KindsOfDatabases/), [SQLAlchemy con MySQL](https://help.pythonanywhere.com/pages/UsingSQLAlchemywithMySQL), [precios](https://www.pythonanywhere.com/pricing/).
- Render: [despliegue gratuito](https://render.com/docs/free), [versión de Python](https://render.com/docs/python-version), [variables y archivos secretos](https://render.com/docs/configure-environment-variables).
- Aiven: [plan gratuito de MySQL](https://aiven.io/docs/products/mysql/concepts/mysql-free-tier).
