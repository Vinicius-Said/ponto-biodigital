document.querySelectorAll('[data-theme-toggle]').forEach(button => {
  button.addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('biodigital-theme', theme); } catch (_) {}
  });
});
const menu = document.querySelector('[data-menu]');
if (menu) menu.addEventListener('click', () => {
  const open = document.body.classList.toggle('menu-open');
  menu.setAttribute('aria-expanded', String(open));
  menu.setAttribute('aria-label', open ? 'Fechar navegação' : 'Abrir navegação');
});
document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
document.querySelectorAll('[data-print]').forEach(button => button.addEventListener('click', () => window.print()));
document.querySelectorAll('[data-period]').forEach(select => {
  select.addEventListener('change', () => {
    const form = select.form;
    form.querySelectorAll('input[type="date"]').forEach(input => { input.readOnly = select.value !== 'custom'; });
  });
  select.dispatchEvent(new Event('change'));
});
document.querySelectorAll('form[data-punch]').forEach(form => {
  form.addEventListener('submit', () => {
    const button = form.querySelector('button');
    button.disabled = true;
    button.textContent = 'Registrando…';
  });
});
const clock = document.querySelector('[data-clock]');
if (clock && clock.dataset.serverNow) {
  const initial = Date.parse(clock.dataset.serverNow);
  const started = performance.now();
  const formatter = new Intl.DateTimeFormat('pt-BR', {timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit', second: '2-digit'});
  if (Number.isFinite(initial)) {
    const tick = () => { clock.textContent = formatter.format(new Date(initial + performance.now() - started)); };
    tick(); setInterval(tick, 1000);
  }
}
