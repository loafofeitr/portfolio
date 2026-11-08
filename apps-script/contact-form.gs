// Копия скрипта из Google-таблицы «Сообщения с сайта» (Расширения → Apps Script).
// При изменениях обновляй код в обоих местах. Подробности: docs/contact-form.md

const SHEET_NAME = 'Сообщения';
const HEADER = ['Дата', 'Имя', 'Email', 'Сообщение'];
const MAX_LENGTH = { name: 100, email: 200, message: 3000 };
const MIN_FILL_MS = 3000;
const KEEP_DAYS = 365;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Запустить один раз вручную: создаёт лист с заголовками и ежедневную очистку.
function setup() {
  getSheet_();
  ScriptApp.getProjectTriggers()
    .filter(function (t) { return t.getHandlerFunction() === 'deleteOldMessages'; })
    .forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('deleteOldMessages').timeBased().everyDays(1).atHour(4).create();
}

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);

    if (data.website || !(Number(data.elapsed) >= MIN_FILL_MS)) {
      return reply_({ ok: true });
    }

    const name = String(data.name || '').replace(/\s+/g, ' ').trim();
    const email = String(data.email || '').trim();
    const message = String(data.message || '').trim();

    if (!name || !email || !message) return reply_({ ok: false, error: 'missing_field' });
    if (name.length > MAX_LENGTH.name || email.length > MAX_LENGTH.email ||
        message.length > MAX_LENGTH.message) return reply_({ ok: false, error: 'too_long' });
    if (!EMAIL_RE.test(email)) return reply_({ ok: false, error: 'bad_email' });
    if (data.consent !== true) return reply_({ ok: false, error: 'no_consent' });

    getSheet_().appendRow([new Date(), asText_(name), asText_(email), asText_(message)]);

    try {
      notify_(name, email, message);
    } catch (err) {
      console.error('Не удалось отправить уведомление: ' + err);
    }
    return reply_({ ok: true });
  } catch (err) {
    console.error(err);
    return reply_({ ok: false, error: 'server_error' });
  }
}

// Запускается триггером раз в сутки: удаляет сообщения старше KEEP_DAYS дней.
function deleteOldMessages() {
  const sheet = getSheet_();
  const cutoff = new Date(Date.now() - KEEP_DAYS * 24 * 60 * 60 * 1000);
  const dates = sheet.getRange(1, 1, sheet.getLastRow(), 1).getValues();
  for (let row = dates.length; row >= 2; row--) {
    const date = dates[row - 1][0];
    if (date instanceof Date && date < cutoff) sheet.deleteRow(row);
  }
}

function getSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) sheet = ss.insertSheet(SHEET_NAME);
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADER);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

// Апостроф в начале не даёт таблице принять текст за формулу.
function asText_(value) {
  return /^[=+\-@\t\r]/.test(value) ? "'" + value : value;
}

function notify_(name, email, message) {
  MailApp.sendEmail({
    to: Session.getEffectiveUser().getEmail(),
    replyTo: email,
    name: 'Форма на сайте',
    subject: 'Новое сообщение с сайта от ' + name,
    body: 'Имя: ' + name + '\nEmail: ' + email + '\n\n' + message +
      '\n\n---\nВсе сообщения: ' + SpreadsheetApp.getActiveSpreadsheet().getUrl() +
      '\nЧтобы ответить, просто нажмите «Ответить».',
  });
}

function reply_(result) {
  return ContentService.createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
}
