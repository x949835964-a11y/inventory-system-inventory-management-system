from app import create_app, db
from app.models.user import User  # Ajusta esta ruta si tu modelo de usuario está en otra carpeta

app = create_app()

with app.app_context():
    # Crea las tablas si no existen
    db.create_all()
    
    # Crea el usuario administrador por defecto automáticamente si no existe
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        admin = User(username="admin", role="admin") # O ajusta los campos según tu modelo
        admin.set_password("Admin123")
        db.session.add(admin)
        db.session.commit()
        print("¡Usuario administrador creado automáticamente!")

if __name__ == '__main__':
    app.run(debug=True)