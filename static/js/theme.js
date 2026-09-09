// Dark/light mode toggle. The actual theme is already applied before paint
// by a tiny inline script in each page's <head> (reads localStorage) — this
// file just wires up the toggle button and keeps the sun/moon icon in sync.
(function () {
  var toggleBtn = document.getElementById('themeToggle');
  if (!toggleBtn) return;

  var sunIcon = document.getElementById('themeIconSun');
  var moonIcon = document.getElementById('themeIconMoon');

  function syncIcon() {
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (sunIcon) sunIcon.style.display = isDark ? 'none' : 'block';
    if (moonIcon) moonIcon.style.display = isDark ? 'block' : 'none';
  }

  syncIcon();

  toggleBtn.addEventListener('click', function () {
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) {
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('studydeck-theme', 'light');
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('studydeck-theme', 'dark');
    }
    syncIcon();
  });
})();
