(() => {
  const timer = document.getElementById('timer');
  const form = document.getElementById('exam-form');
  if (!timer || !form) return;
  let remaining = Number(timer.dataset.seconds);
  const render = () => {
    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;
    timer.textContent = `${minutes}:${String(seconds).padStart(2, '0')}`;
    if (remaining <= 0) {
      form.requestSubmit();
      return;
    }
    remaining -= 1;
    window.setTimeout(render, 1000);
  };
  render();
})();
