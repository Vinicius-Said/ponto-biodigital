import click
from flask.cli import with_appcontext
from app.extensions import db
from app.services.audit import prune_logs
from app.services.schedules import seed_schedules


def register_commands(app):
    @app.cli.command("seed")
    @with_appcontext
    def seed():
        """Create the three default schedules; never create a default password."""
        seed_schedules()
        db.session.commit()
        click.echo("Jornadas iniciais criadas. Configure o primeiro diretor em /setup com seu SETUP_TOKEN.")

    @app.cli.command("prune-logs")
    @with_appcontext
    def prune():
        """Delete administrative logs older than three calendar months."""
        count = prune_logs()
        click.echo(f"{count} logs anteriores a três meses removidos. Pontos e correções preservados.")
