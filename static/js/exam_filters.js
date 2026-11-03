(() => {
  const cards = [...document.querySelectorAll('[data-exam-card]')];
  if (!cards.length) return;
  const search = document.getElementById('exam-search');
  const chips = [...document.querySelectorAll('[data-status-filter]')];
  const empty = document.getElementById('filter-empty');
  let status = 'all';
  const update = () => {
    const query = (search?.value || '').trim().toLowerCase();
    let visible = 0;
    cards.forEach((card) => {
      const statusMatches = status === 'all' || card.dataset.status === status;
      const textMatches = (card.dataset.search || '').toLowerCase().includes(query);
      card.hidden = !(statusMatches && textMatches);
      if (!card.hidden) visible += 1;
    });
    if (empty) empty.hidden = visible > 0;
  };
  chips.forEach((chip) => chip.addEventListener('click', () => {
    status = chip.dataset.statusFilter;
    chips.forEach((item) => item.classList.toggle('active', item === chip));
    update();
  }));
  search?.addEventListener('input', update);
})();
