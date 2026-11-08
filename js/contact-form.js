// Адрес веб-приложения Google Apps Script (см. docs/contact-form.md). Не секретный.
const CONTACT_FORM_URL = '';
const CONTACT_FORM_TIMEOUT_MS = 15000;

(function () {
  const form = document.getElementById('contact-form');
  const thanks = document.getElementById('thanks');
  const error = document.getElementById('form-error');
  const button = form.querySelector('button[type="submit"]');
  const buttonText = button.textContent;
  const openedAt = Date.now();

  function setSending(sending) {
    button.disabled = sending;
    button.textContent = sending ? 'Отправляем…' : buttonText;
  }

  async function send(data) {
    if (!CONTACT_FORM_URL) throw new Error('CONTACT_FORM_URL is not set');
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, CONTACT_FORM_TIMEOUT_MS);
    try {
      const response = await fetch(CONTACT_FORM_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
        body: JSON.stringify(data),
        signal: controller.signal,
      });
      const result = await response.json();
      if (!result.ok) throw new Error(result.error || 'unknown error');
    } finally {
      clearTimeout(timer);
    }
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    error.hidden = true;
    setSending(true);
    try {
      await send({
        name: form.elements.name.value,
        email: form.elements.email.value,
        message: form.elements.message.value,
        consent: form.elements.consent.checked,
        website: form.elements.website.value,
        elapsed: Date.now() - openedAt,
      });
      form.style.display = 'none';
      thanks.style.display = 'block';
    } catch (err) {
      console.error(err);
      error.hidden = false;
      setSending(false);
    }
  });
})();
