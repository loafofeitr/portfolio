// Адрес веб-приложения Google Apps Script (см. docs/contact-form.md). Не секретный.
const CONTACT_FORM_URL = 'https://script.google.com/macros/s/AKfycbzrSkl71rhrKknSRmYWqc4325CpgmqcYEYdifqcNZY0yNPID-iJ9Q4b_329rY-sm0UA/exec';
const CONTACT_FORM_TIMEOUT_MS = 15000;
const MESSAGE_MAX_LENGTH = 1000;

(function () {
  const form = document.getElementById('contact-form');
  const thanks = document.getElementById('thanks');
  const error = document.getElementById('form-error');
  const button = form.querySelector('button[type="submit"]');
  const buttonText = button.textContent;
  const openedAt = Date.now();
  const message = form.elements.message;
  const counter = document.getElementById('message-counter');
  const lengthError = document.getElementById('message-error');

  // Считаем так же, как скрипт Google: без пробелов по краям.
  function checkLength() {
    const length = message.value.trim().length;
    const tooLong = length > MESSAGE_MAX_LENGTH;
    counter.textContent = length + ' / ' + MESSAGE_MAX_LENGTH;
    counter.classList.toggle('over', tooLong);
    lengthError.hidden = !tooLong;
    return !tooLong;
  }

  message.addEventListener('input', checkLength);
  checkLength();

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
    if (!checkLength()) {
      message.focus();
      return;
    }
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
