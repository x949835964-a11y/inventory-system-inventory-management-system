"""Custom Flask CLI commands."""
import click
from flask import Flask

from app.models import UserRole
from app.services.exceptions import BusinessRuleError
from app.services.user_service import create_user
from app.utils.security import password_problem


def register_cli(app: Flask) -> None:
    @app.cli.command("create-admin")
    @click.option("--username", prompt="Usuario")
    @click.option("--full-name", prompt="Nombre completo")
    @click.password_option("--password", prompt="Contraseña", confirmation_prompt="Repite la contraseña")
    def create_admin(username: str, full_name: str, password: str) -> None:
        """Create an administrator (needed once, before the first login)."""
        problem = password_problem(password)
        if problem:
            raise click.ClickException(problem)
        try:
            user = create_user(username=username, full_name=full_name, password=password, role=UserRole.ADMIN)
        except BusinessRuleError as exc:
            raise click.ClickException(str(exc)) from None
        click.echo(f"Administrador '{user.username}' creado.")

    @app.cli.command("seed")
    @click.option("--reset", is_flag=True, help="Borra TODOS los datos antes de cargar la demo.")
    @click.option("--yes", is_flag=True, help="No pide confirmación al usar --reset.")
    @click.option("--days", default=45, show_default=True, type=click.IntRange(7, 365), help="Días de historial a simular.")
    def seed(reset: bool, yes: bool, days: int) -> None:
        """Load demo data: users, catalog and ~45 days of movements."""
        from app.demo import DEMO_ACCOUNTS
        from app.seed import clear_all_data, has_data, seed_demo_data

        if has_data():
            if not reset:
                raise click.ClickException("La base de datos ya tiene datos. Usa --reset para borrarlos y cargar la demo.")
            if not yes:
                click.confirm("Se borrarán TODOS los usuarios, productos y movimientos. ¿Continuar?", abort=True)
            clear_all_data()
            click.echo("Datos anteriores eliminados.")

        click.echo(f"Generando {days} días de movimientos...")
        summary = seed_demo_data(days=days)
        click.echo(
            f"Listo: {summary['products']} productos, {summary['categories']} categorías, "
            f"{summary['suppliers']} proveedores y {summary['movements']} movimientos. "
            f"En alerta: {summary['low_stock']} (agotados: {summary['out_of_stock']})."
        )
        click.echo("Usuarios demo:")
        for username, _name, role, password in DEMO_ACCOUNTS:
            click.echo(f"  {role.label:<14} usuario: {username:<10} contraseña: {password}")
