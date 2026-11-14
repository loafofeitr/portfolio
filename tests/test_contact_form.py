"""Автотесты формы обратной связи. Запуск: python3 -m unittest discover tests
Подробности — docs/tests.md."""

import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request

from websockets.sync.client import connect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME_PORT = 9333
LIMIT = 1000

# Подменяет отправку: вместо Google запросы записываются в window.__sent.
STUB_FETCH = """
window.__sent = [];
window.fetch = async function (url, options) {
  window.__sent.push(options.body);
  return { json: async function () { return { ok: true }; } };
};
"""

STATE = """
(function () {
  function visible(el) {
    return !!el && !el.hidden && getComputedStyle(el).display !== 'none';
  }
  const counter = document.getElementById('message-counter');
  const error = document.getElementById('message-error');
  const message = document.getElementById('message');
  return {
    counterText: counter ? counter.textContent.trim() : null,
    counterOver: counter ? counter.classList.contains('over') : null,
    errorVisible: visible(error),
    errorText: error ? error.textContent.trim() : null,
    formVisible: visible(document.getElementById('contact-form')),
    thanksVisible: visible(document.getElementById('thanks')),
    messageLength: message.value.length,
    hasMaxlength: message.hasAttribute('maxlength'),
    sent: window.__sent.length,
  };
})()
"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class ContactFormTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(QuietHandler, directory=ROOT)
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = 'http://127.0.0.1:%d/index.html' % cls.server.server_port

        cls.profile = tempfile.mkdtemp()
        chrome = shutil.which('google-chrome') or shutil.which('chromium')
        cls.chrome = subprocess.Popen(
            [chrome, '--headless=new', '--disable-gpu', '--no-first-run',
             '--remote-debugging-port=%d' % CHROME_PORT,
             '--user-data-dir=' + cls.profile, 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.ws = connect(cls._page_ws_url(), max_size=None)
        cls.msg_id = 0

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()
        cls.chrome.terminate()
        cls.chrome.wait()
        shutil.rmtree(cls.profile, ignore_errors=True)
        cls.server.shutdown()

    @staticmethod
    def _page_ws_url():
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                with urllib.request.urlopen('http://127.0.0.1:%d/json' % CHROME_PORT) as r:
                    for target in json.load(r):
                        if target['type'] == 'page':
                            return target['webSocketDebuggerUrl']
            except OSError:
                pass
            time.sleep(0.2)
        raise RuntimeError('Chrome не запустился')

    def cdp(self, method, **params):
        cls = type(self)
        cls.msg_id += 1
        self.ws.send(json.dumps({'id': cls.msg_id, 'method': method, 'params': params}))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get('id') == cls.msg_id:
                if 'error' in reply:
                    raise RuntimeError(reply['error'])
                return reply['result']

    def js(self, expression):
        result = self.cdp('Runtime.evaluate', expression=expression,
                          awaitPromise=True, returnByValue=True)
        if 'exceptionDetails' in result:
            raise RuntimeError(result['exceptionDetails'])
        return result['result'].get('value')

    def setUp(self):
        self.cdp('Page.navigate', url=self.url)
        deadline = time.time() + 10
        while self.js('document.readyState') != 'complete':
            if time.time() > deadline:
                raise RuntimeError('страница не загрузилась')
            time.sleep(0.05)
        self.js(STUB_FETCH)

    def type_message(self, text):
        self.js("""(function () {
          const m = document.getElementById('message');
          m.value = %s;
          m.dispatchEvent(new Event('input', { bubbles: true }));
        })()""" % json.dumps(text))

    def fill_and_submit(self, text):
        self.js("""(function () {
          const f = document.getElementById('contact-form');
          f.elements.name.value = 'Тест';
          f.elements.email.value = 'test@example.com';
          f.elements.consent.checked = true;
        })()""")
        self.type_message(text)
        self.js("document.getElementById('contact-form').requestSubmit()")
        self.js("new Promise(function (r) { setTimeout(r, 200); })")
        return self.js(STATE)

    def state(self):
        return self.js(STATE)

    def test_counter_starts_at_zero(self):
        self.assertEqual(self.state()['counterText'], '0 / 1000')

    def test_counter_updates_while_typing(self):
        self.type_message('Привет')
        self.assertEqual(self.state()['counterText'], '6 / 1000')

    def test_counter_ignores_spaces_at_edges(self):
        self.type_message('  ab  \n')
        self.assertEqual(self.state()['counterText'], '2 / 1000')

    def test_can_type_more_than_limit(self):
        self.type_message('a' * 1500)
        state = self.state()
        self.assertFalse(state['hasMaxlength'])
        self.assertEqual(state['messageLength'], 1500)

    def test_exactly_limit_is_sent(self):
        state = self.fill_and_submit('a' * LIMIT)
        self.assertEqual(state['counterText'], '1000 / 1000')
        self.assertIs(state['counterOver'], False)
        self.assertFalse(state['errorVisible'])
        self.assertEqual(state['sent'], 1)
        self.assertTrue(state['thanksVisible'])

    def test_over_limit_shows_error_while_typing(self):
        self.type_message('a' * (LIMIT + 1))
        state = self.state()
        self.assertEqual(state['counterText'], '1001 / 1000')
        self.assertTrue(state['counterOver'])
        self.assertTrue(state['errorVisible'])
        self.assertEqual(state['errorText'],
                         'Сообщение слишком длинное: максимум 1000 символов')

    def test_over_limit_is_not_sent(self):
        state = self.fill_and_submit('a' * (LIMIT + 1))
        self.assertEqual(state['sent'], 0)
        self.assertTrue(state['errorVisible'])
        self.assertTrue(state['formVisible'])
        self.assertFalse(state['thanksVisible'])
        self.assertEqual(state['messageLength'], LIMIT + 1)

    def test_error_disappears_after_shortening(self):
        self.type_message('a' * (LIMIT + 1))
        self.assertTrue(self.state()['errorVisible'])
        self.type_message('a' * LIMIT)
        state = self.state()
        self.assertIs(state['counterOver'], False)
        self.assertFalse(state['errorVisible'])


class AppsScriptLimitTest(unittest.TestCase):
    def test_apps_script_message_limit_is_1000(self):
        with open(os.path.join(ROOT, 'apps-script', 'contact-form.gs'), encoding='utf-8') as f:
            code = f.read()
        self.assertRegex(code, r'MAX_LENGTH\s*=\s*\{[^}]*\bmessage:\s*1000\b')


if __name__ == '__main__':
    unittest.main()
