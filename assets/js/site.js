// Grid filter tabs
document.querySelectorAll('.tabs button').forEach(btn => {
  btn.addEventListener('click', () => {
    const f = btn.dataset.filter;
    document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.grid .tile').forEach(t => {
      const show = f === 'all' || (f === 'video' ? t.hasAttribute('data-video') : t.dataset.source === f);
      t.hidden = !show;
    });
  });
});

// Post carousel: arrows, dots, keyboard
document.querySelectorAll('.media').forEach(media => {
  const track = media.querySelector('.carousel');
  const dots = media.querySelectorAll('.dots span');
  if (!track) return;
  const idx = () => Math.round(track.scrollLeft / track.clientWidth);
  const go = i => {
    track.querySelectorAll('video').forEach(v => v.pause());
    track.scrollTo({ left: i * track.clientWidth, behavior: 'smooth' });
  };
  media.querySelector('.prev')?.addEventListener('click', () => go(idx() - 1));
  media.querySelector('.next')?.addEventListener('click', () => go(idx() + 1));
  track.addEventListener('scroll', () => dots.forEach((d, i) => d.classList.toggle('on', i === idx())), { passive: true });
  document.addEventListener('keydown', e => {
    if (e.key === 'ArrowRight') go(idx() + 1);
    if (e.key === 'ArrowLeft') go(idx() - 1);
  });
});
