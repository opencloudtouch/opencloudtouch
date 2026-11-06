"""Execute the actual Actions fetch blocks against a local Basic-Auth fixture."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

REPO = Path(os.environ.get('OCT_SOURCE_REPO', Path(__file__).resolve().parents[2]))
FIXTURE = b'name,type,amount,monthlyAmount,firstSupportDate\nFixture,monthly,8,1,2026-06-02\n'


def fetch_block(path):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    start = next(i for i, line in enumerate(lines) if '- name: Fetch supporters' in line)
    start = next(i for i in range(start, len(lines)) if lines[i].strip() == 'run: |') + 1
    result = []
    for line in lines[start:]:
        if line and not line.startswith('          '):
            break
        result.append(line[10:] if line else '')
    return '\n'.join(result) + '\n'


class SupportersFetchTests(unittest.TestCase):
    def test_workflow_fetches_with_short_and_rotated_length_passwords(self):
        if os.name == 'nt':
            git_root = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Git'
            bash = git_root / 'bin/bash.exe'
            tool_paths = [str(git_root / 'usr/bin'), str(git_root / 'mingw64/bin')]
        else:
            bash = Path(shutil.which('bash') or '/bin/bash')
            tool_paths = []
        self.assertTrue(bash.exists(), 'Bash and curl are required for workflow regression tests')

        for filename in ['patch-supporters.yml', 'build-images.yml', 'test-build.yml']:
            script = fetch_block(REPO / '.github/workflows' / filename)
            for password in ['short-test-password', 'A' * 64]:
                with self.subTest(workflow=filename, password_length=len(password)):
                    auth = 'Basic ' + base64.b64encode(('oct-ci:' + password).encode()).decode()
                    accepted = []

                    class Handler(BaseHTTPRequestHandler):
                        def do_GET(self):
                            if self.headers.get('Authorization') != auth:
                                self.send_response(401)
                                self.end_headers()
                                return
                            accepted.append(True)
                            self.send_response(200)
                            self.send_header('Content-Length', str(len(FIXTURE)))
                            self.end_headers()
                            self.wfile.write(FIXTURE)

                        def log_message(self, *args):
                            pass

                    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
                    worker = threading.Thread(target=server.serve_forever, daemon=True)
                    worker.start()
                    try:
                        with tempfile.TemporaryDirectory(prefix='oct-fetch-') as folder:
                            root = Path(folder)
                            (root / 'apps/frontend/public').mkdir(parents=True)
                            url = f'http://127.0.0.1:{server.server_port}/supporters.csv'
                            actual = script.replace('https://opencloudtouch.org/api/supporters/get.php', url)
                            shell_file = root / 'fetch.sh'
                            shell_file.write_bytes(actual.encode('utf-8'))
                            env = dict(os.environ, SUPPORTERS_API_USER='oct-ci', SUPPORTERS_API_PASS=password)
                            env['PATH'] = os.pathsep.join(tool_paths + [env.get('PATH', '')])
                            result = subprocess.run([str(bash), '--noprofile', '--norc', '-e', shell_file.as_posix()],
                                                    cwd=root, env=env, capture_output=True, timeout=20)
                            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
                            target = root / ('supporters.csv' if filename == 'patch-supporters.yml'
                                             else 'apps/frontend/public/supporters.csv')
                            self.assertEqual(target.read_bytes(), FIXTURE)
                            self.assertEqual(len(accepted), 1)
                    finally:
                        server.shutdown()
                        server.server_close()
                        worker.join(timeout=3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
