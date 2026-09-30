"""Optional UI verification with a temporary SQLite database and a local HTTP server.

Install playwright and its Chromium before running this script. No operational
DATABASE_URL is used and no default application credentials are created.
"""

import importlib
import re
import secrets
import sys
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flask_migrate import upgrade  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Employee, TimeRecord  # noqa: E402
from app.services.clock import local_time, today, to_utc, utc_now  # noqa: E402


def verify_browser():
    artifacts = ROOT / "tmp" / "ui"
    artifacts.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(24)
    setup_token = secrets.token_urlsafe(48)
    errors = []
    with TemporaryDirectory(prefix="ponto-ui-") as temporary:
        app = create_app(
            {
                "TESTING": True,
                "APP_ENV": "development",
                "SECRET_KEY": secrets.token_urlsafe(48),
                "SETUP_TOKEN": setup_token,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{temporary}/ui.db",
                "SESSION_COOKIE_SECURE": False,
                "APPLICATION_ROOT": "/",
            }
        )
        with app.app_context():
            upgrade(directory=str(ROOT / "migrations"))
            day = today()
        server = make_server("127.0.0.1", 0, app, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
                admin = browser.new_context(viewport={"width": 1440, "height": 1000}, color_scheme="light")
                page = admin.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/setup")
                page.get_by_label("Token de configuração").fill(setup_token)
                page.get_by_label("Usuário", exact=True).fill("diretor_teste")
                page.get_by_label("Senha", exact=True).fill(password)
                page.get_by_label("Confirmar senha").fill(password)
                page.get_by_role("button", name="Criar primeiro diretor").click()
                page.wait_for_url("**/login")
                page.screenshot(path=str(artifacts / "login-desktop.png"), full_page=True, animations="disabled")
                page.get_by_label("Usuário", exact=True).fill("diretor_teste")
                page.get_by_label("Senha", exact=True).fill(password)
                page.get_by_role("button", name="Entrar", exact=True).click()
                page.wait_for_url("**/dashboard/")
                page.get_by_role("link", name="+ Novo funcionário", exact=True).click()
                page.get_by_label("Nome completo").fill("Ana de Teste")
                page.get_by_label("Início do controle de ponto").fill(day.replace(day=1).isoformat())
                page.get_by_label("Usuário", exact=True).fill("ana_teste")
                page.get_by_label("Senha inicial").fill(password)
                page.get_by_role("button", name="Cadastrar funcionário", exact=True).click()
                page.wait_for_url(re.compile(r"/employees/\d+$"))
                with app.app_context():
                    employee = db.session.scalar(db.select(Employee).where(Employee.name == "Ana de Teste"))
                    stamp = day.replace(day=1)
                    while stamp < day:
                        if stamp.weekday() < 5:
                            for kind, hour in [
                                ("ENTRADA", 8),
                                ("INTERVALO_SAIDA", 12),
                                ("INTERVALO_RETORNO", 13),
                                ("SAIDA", 17),
                            ]:
                                db.session.add(
                                    TimeRecord(
                                        employee_id=employee.id,
                                        work_date=stamp,
                                        type=kind,
                                        recorded_at=to_utc(
                                            datetime.combine(stamp, datetime.min.time()).replace(hour=hour)
                                        ),
                                        ip_address="127.0.0.1",
                                    )
                                )
                        stamp += timedelta(days=1)
                    db.session.commit()
                page.goto(base + "/dashboard/")
                page.screenshot(path=str(artifacts / "director-desktop.png"), full_page=True, animations="disabled")
                employee_context = browser.new_context(viewport={"width": 1440, "height": 1000}, color_scheme="light")
                employee_page = employee_context.new_page()
                employee_page.on("pageerror", lambda error: errors.append(str(error)))
                employee_page.goto(base + "/login")
                employee_page.get_by_label("Usuário", exact=True).fill("ana_teste")
                employee_page.get_by_label("Senha", exact=True).fill(password)
                employee_page.get_by_role("button", name="Entrar", exact=True).click()
                employee_page.wait_for_url("**/dashboard/")
                employee_page.get_by_role("button", name=re.compile("Registrar entrada")).click()
                employee_page.wait_for_url("**/dashboard/")
                assert employee_page.get_by_text("Entrada registrada pelo horário do servidor.").is_visible()
                employee_page.screenshot(
                    path=str(artifacts / "employee-desktop.png"), full_page=True, animations="disabled"
                )
                employee_page.get_by_role("button", name="Alternar tema claro e escuro").click()
                employee_page.reload()
                assert employee_page.locator("html").get_attribute("data-theme") == "dark"
                employee_page.screenshot(
                    path=str(artifacts / "employee-dark.png"), full_page=True, animations="disabled"
                )
                employee_page.set_viewport_size({"width": 390, "height": 844})
                assert employee_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                employee_page.screenshot(
                    path=str(artifacts / "employee-mobile.png"), full_page=True, animations="disabled"
                )
                employee_page.get_by_role("button", name="Abrir navegação").click()
                employee_page.get_by_role("link", name="Correções", exact=True).click()
                employee_page.get_by_role("link", name="+ Solicitar correção", exact=True).click()
                with app.app_context():
                    value = local_time(utc_now()) - timedelta(minutes=1)
                employee_page.get_by_label("Horário solicitado").fill(value.strftime("%H:%M"))
                employee_page.get_by_label("Motivo", exact=True).fill(
                    "Horário conferido durante a homologação do sistema."
                )
                employee_page.get_by_role("button", name="Enviar solicitação", exact=True).click()
                employee_page.wait_for_url(re.compile(r"/corrections/\d+$"))
                correction_path = employee_page.url.removeprefix(base)
                assert employee_page.get_by_text("Aguardando análise", exact=True).is_visible()
                page.goto(base + correction_path)
                page.get_by_label("Decisão", exact=True).select_option("APROVADO")
                page.get_by_label("Justificativa da decisão").fill("Horário confirmado em homologação.")
                page.once("dialog", lambda dialog: dialog.accept())
                page.get_by_role("button", name="Confirmar decisão", exact=True).click()
                assert page.get_by_text("Decisão registrada", exact=True).is_visible()
                page.goto(base + "/reports/?employee_id=0&period=month")
                page.screenshot(path=str(artifacts / "report-desktop.png"), full_page=True, animations="disabled")
                with page.expect_download() as download:
                    page.get_by_role("link", name="Baixar PDF", exact=True).click()
                download.value.save_as(str(artifacts / "report-sample.pdf"))
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(base + "/dashboard/")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(artifacts / "director-mobile.png"), full_page=True, animations="disabled")
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
    print("UI verificada: setup, login, cadastro, ponto, tema persistente, mobile, solicitação, aprovação e PDF.")
    print("Screenshots e PDF de homologação em tmp/ui (fora do Git).")


def run():
    # Keep this disposable UI scenario independent of weekends and local time.
    now = datetime(2026, 9, 30, 20, 0)
    modules = [
        __name__,
        "app.services.clock",
        "app.services.attendance",
        "app.services.corrections",
        "app.services.time_calculator",
        "app.services.history",
        "app.services.schedules",
        "app.services.audit",
        "app.services.pdf_report",
        "app.auth.routes",
        "app.dashboard.routes",
    ]
    with ExitStack() as clock:
        for name in modules:
            module = importlib.import_module(name)
            if hasattr(module, "utc_now"):
                clock.enter_context(patch.object(module, "utc_now", lambda: now))
        verify_browser()


if __name__ == "__main__":
    run()
