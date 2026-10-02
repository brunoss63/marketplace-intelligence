import json
import tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


_SEGREDOS = tomllib.loads(
    Path(".streamlit/secrets.toml").read_text(encoding="utf-8")
)
_SUPABASE_URL = str(_SEGREDOS["SUPABASE_DEV_URL"]).rstrip("/")
_SUPABASE_ANON_KEY = str(_SEGREDOS["SUPABASE_DEV_ANON_KEY"])
_HOSTS_LOCAIS = {"localhost:3000", "127.0.0.1:3000"}
_ORIGENS_LOCAIS = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}

if urlparse(_SUPABASE_URL).scheme != "https":
    raise ValueError("SUPABASE_DEV_URL precisa usar HTTPS.")
if not _SUPABASE_URL.endswith(".supabase.co"):
    raise ValueError("SUPABASE_DEV_URL não aponta para um projeto Supabase.")
if not _SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_DEV_ANON_KEY está vazia.")


_PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Redefinir senha - Marketplace Intelligence DEV</title>
  <style>
    body { font: 16px system-ui, sans-serif; margin: 3rem auto; max-width: 28rem; padding: 0 1rem; color: #17202a; }
    label { display: block; margin-top: 1rem; }
    input, button { box-sizing: border-box; font: inherit; margin-top: .4rem; padding: .7rem; width: 100%; }
    button { cursor: pointer; margin-top: 1.2rem; }
    #message { margin-top: 1rem; }
  </style>
</head>
<body>
  <h1>Redefinir senha</h1>
  <p>Este formulário altera somente a senha da conta de desenvolvimento.</p>
  <form id="form" hidden>
    <label>Nova senha
      <input id="password" type="password" autocomplete="new-password" minlength="8" required>
    </label>
    <label>Confirme a nova senha
      <input id="confirmation" type="password" autocomplete="new-password" minlength="8" required>
    </label>
    <button id="submit" type="submit">Salvar nova senha</button>
  </form>
  <p id="message" role="status">Validando o link...</p>
  <script>
    const params = new URLSearchParams(window.location.hash.slice(1));
    const accessToken = params.get("access_token");
    const recoveryType = params.get("type");
    window.history.replaceState(null, "", window.location.pathname);

    const form = document.getElementById("form");
    const message = document.getElementById("message");
    if (accessToken && recoveryType === "recovery") {
      form.hidden = false;
      message.textContent = "Escolha uma senha nova com pelo menos 8 caracteres.";
    } else {
      message.textContent = "Link inválido ou expirado. Solicite outro link de recuperação.";
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const password = document.getElementById("password").value;
      const confirmation = document.getElementById("confirmation").value;
      if (password.length < 8) {
        message.textContent = "A senha precisa ter pelo menos 8 caracteres.";
        return;
      }
      if (password !== confirmation) {
        message.textContent = "As senhas não coincidem.";
        return;
      }

      const submit = document.getElementById("submit");
      submit.disabled = true;
      message.textContent = "Salvando a nova senha...";
      try {
        const response = await fetch("/reset", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({access_token: accessToken, password}),
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || "Não foi possível atualizar a senha.");
        }
        form.hidden = true;
        message.textContent = "Senha atualizada. Agora entre no app de desenvolvimento.";
        const link = document.createElement("a");
        link.href = "http://127.0.0.1:8501";
        link.textContent = "Abrir o app DEV";
        message.appendChild(document.createElement("br"));
        message.appendChild(link);
      } catch (error) {
        message.textContent = error.message;
        submit.disabled = false;
      }
    });
  </script>
</body>
</html>
""".encode("utf-8")


class _Manipulador(BaseHTTPRequestHandler):
    server_version = "LocalPasswordReset"

    def do_GET(self) -> None:
        if self.path != "/" or self.headers.get("Host") not in _HOSTS_LOCAIS:
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; "
            "script-src 'unsafe-inline'; connect-src 'self'; "
            "form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(_PAGINA)

    def do_POST(self) -> None:
        if (
            self.path != "/reset"
            or self.headers.get("Host") not in _HOSTS_LOCAIS
            or self.headers.get("Origin") not in _ORIGENS_LOCAIS
        ):
            self._responder(403, {"error": "Origem não permitida."})
            return

        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
            if tamanho <= 0 or tamanho > 16_384:
                self._responder(400, {"error": "Pedido inválido."})
                return
            dados = json.loads(self.rfile.read(tamanho))
        except (ValueError, json.JSONDecodeError):
            self._responder(400, {"error": "Pedido inválido."})
            return

        token = dados.get("access_token") if isinstance(dados, dict) else None
        senha = dados.get("password") if isinstance(dados, dict) else None
        if (
            not isinstance(token, str)
            or not token
            or not isinstance(senha, str)
            or len(senha) < 8
        ):
            self._responder(400, {"error": "Link ou senha inválidos."})
            return

        request = Request(
            f"{_SUPABASE_URL}/auth/v1/user",
            data=json.dumps({"password": senha}).encode("utf-8"),
            headers={
                "apikey": _SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        try:
            with urlopen(request, timeout=15) as response:
                if response.status != 200:
                    self._responder(
                        502,
                        {"error": "O Supabase não confirmou a troca da senha."},
                    )
                    return
        except HTTPError:
            self._responder(
                400,
                {
                    "error": (
                        "O link expirou ou a senha foi recusada. "
                        "Solicite um novo link ou escolha outra senha."
                    )
                },
            )
            return
        except URLError:
            self._responder(
                502,
                {"error": "Não foi possível contatar o Supabase. Tente novamente."},
            )
            return

        self._responder(200, {"ok": True})

    def _responder(self, status: int, corpo: dict[str, str]) -> None:
        payload = json.dumps(corpo).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        print(f"Recuperação DEV: {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 3000), _Manipulador)
    print("Recuperação de senha DEV disponível em http://localhost:3000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor de recuperação DEV encerrado.")
    finally:
        server.server_close()
