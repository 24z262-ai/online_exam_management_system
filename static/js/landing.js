(() => {
  document.documentElement.classList.add('js-motion');
  const demoTabs = [...document.querySelectorAll('[data-demo-mode]')];
  const demoPanels = [...document.querySelectorAll('[data-demo-panel]')];
  const demoCopy = {
    student: {
      eyebrow: 'STUDENT WORKSPACE',
      title: 'Your next step is ready.',
      caption: 'A dedicated home for exams and progress.',
    },
    admin: {
      eyebrow: 'ADMIN WORKSPACE',
      title: 'Your exams, at a glance.',
      caption: 'Create examinations and follow results in one place.',
    },
  };
  demoTabs.forEach((tab) => tab.addEventListener('click', () => {
    const mode = tab.dataset.demoMode;
    demoTabs.forEach((item) => {
      const active = item === tab;
      item.classList.toggle('active', active);
      item.setAttribute('aria-pressed', String(active));
    });
    demoPanels.forEach((panel) => { panel.hidden = panel.dataset.demoPanel !== mode; });
    const copy = demoCopy[mode];
    document.getElementById('demo-eyebrow').textContent = copy.eyebrow;
    document.getElementById('demo-title').textContent = copy.title;
    document.getElementById('demo-caption').textContent = copy.caption;
  }));

  const workflowTabs = [...document.querySelectorAll('[data-workflow]')];
  const workflowPanels = [...document.querySelectorAll('[data-workflow-panel]')];
  workflowTabs.forEach((tab) => tab.addEventListener('click', () => {
    const mode = tab.dataset.workflow;
    workflowTabs.forEach((item) => {
      const active = item === tab;
      item.classList.toggle('active', active);
      item.setAttribute('aria-selected', String(active));
    });
    workflowPanels.forEach((panel) => {
      const active = panel.dataset.workflowPanel === mode;
      panel.hidden = !active;
      panel.classList.toggle('active', active);
    });
  }));

  const revealItems = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    revealItems.forEach((item) => observer.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add('is-visible'));
  }
})();
