from app import create_app, db

app = create_app()

with app.app_context():
    db.create_all()
    # Esto imprimirá todas las rutas disponibles en los logs de Render
    print("--- RUTAS DISPONIBLES EN LA APP ---")
    for rule in app.url_map.iter_rules():
        print(rule, "-->", rule.endpoint)

if __name__ == '__main__':
    app.run(debug=True)