(() => {
  const input = document.getElementById('student-search');
  const rows = [...document.querySelectorAll('[data-student-row]')];
  const empty = document.getElementById('student-empty');
  input?.addEventListener('input', () => {
    const query = input.value.trim().toLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      row.hidden = !(row.dataset.search || '').toLowerCase().includes(query);
      if (!row.hidden) visible += 1;
    });
    if (empty) empty.hidden = visible > 0;
  });
})();
