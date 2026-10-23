/* Copy the short repository task name accepted by --task. */
(() => {
  function legacyCopy(text) {
    const focused = document.activeElement;
    const field = document.createElement('textarea');
    field.value = text;
    field.readOnly = true;
    field.style.cssText = 'position:fixed;left:-9999px;top:0';
    document.body.append(field);
    field.select();
    try {
      if (!document.execCommand('copy')) throw new Error('Copy unavailable');
    } finally {
      field.remove();
      if (focused) focused.focus({ preventScroll: true });
    }
  }

  document.querySelectorAll('.copy-task-name').forEach((button) => {
    button.hidden = false;
    let reset;
    button.addEventListener('click', async () => {
      clearTimeout(reset);
      const name = button.dataset.taskName;
      const status = button.parentElement.querySelector('.copy-status');
      button.disabled = true;
      try {
        try {
          if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
          await navigator.clipboard.writeText(name);
        } catch {
          // HTTP previews may not expose the modern clipboard API.
          legacyCopy(name);
        }
        button.textContent = 'Copied';
        status.textContent = `Copied ${name}`;
      } catch {
        button.textContent = 'Copy failed';
        status.textContent = 'Copy unavailable. Select the task name and copy it manually.';
      } finally {
        button.disabled = false;
        reset = setTimeout(() => {
          button.textContent = 'Copy';
          status.textContent = '';
        }, 2500);
      }
    });
  });
})();
