(() => {
  let theme;
  try { theme = localStorage.getItem('biodigital-theme'); } catch (_) {}
  if (!theme) theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme === 'dark' ? 'dark' : 'light';
})();
