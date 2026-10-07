(() => {
  const appWindow = window.parent;
  const browserWindow = window.top;
  const params = new URLSearchParams(browserWindow.location.hash.slice(1));
  const accessToken = params.get("access_token");
  const flowType = params.get("type");
  const query = new URLSearchParams(browserWindow.location.search);
  const hasAuthError = ["error", "error_description", "error_code"]
    .some((key) => params.has(key) || query.has(key));
  if (!["invite", "recovery"].includes(flowType) && !hasAuthError) {
    if (window.frameElement) window.frameElement.hidden = true;
    return;
  }

  browserWindow.history.replaceState(
    null,
    "",
    browserWindow.location.pathname + browserWindow.location.search,
  );
  appWindow.history.replaceState(
    null,
    "",
    appWindow.location.pathname + appWindow.location.search,
  );

  const flow = document.getElementById("mi-auth-password-flow");
  const message = document.getElementById("mi-auth-password-message");
  const form = document.getElementById("mi-auth-password-form");
  if (window.frameElement) window.frameElement.style.height = "440px";
  flow.hidden = false;
  const hideLogin = () => {
    if (appWindow === window) return true;
    const loginRow = appWindow.document
      .querySelector(".st-key-mi-login-card")
      ?.closest('[data-testid="stHorizontalBlock"]');
    if (!loginRow) return false;
    loginRow.hidden = true;
    return true;
  };
  if (appWindow !== window && !hideLogin()) {
    const observer = new MutationObserver(() => {
      if (hideLogin()) observer.disconnect();
    });
    observer.observe(appWindow.document.body, {
      childList: true,
      subtree: true,
    });
  }

  if (!accessToken || hasAuthError) {
    message.textContent =
      "Este link é inválido ou expirou. Solicite um novo link.";
    return;
  }

  const config = new URLSearchParams(window.location.search);
  const supabaseUrl = config.get("supabase_url");
  const publicKey = config.get("supabase_public_key");
  if (!supabaseUrl || !publicKey) {
    message.textContent =
      "Não foi possível carregar a configuração de senha. Tente novamente.";
    return;
  }

  form.hidden = false;
  message.textContent = "Escolha uma senha com pelo menos 12 caracteres.";
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = document.getElementById("mi-auth-password").value;
    const confirmation =
      document.getElementById("mi-auth-password-confirm").value;
    if (password.length < 12 || password !== confirmation) {
      message.textContent =
        password !== confirmation
          ? "As senhas não coincidem."
          : "A senha precisa ter pelo menos 12 caracteres.";
      return;
    }

    const submit = document.getElementById("mi-auth-password-submit");
    submit.disabled = true;
    message.textContent = "Salvando a senha...";
    try {
      const response = await fetch(`${supabaseUrl}/auth/v1/user`, {
        method: "PUT",
        headers: {
          apikey: publicKey,
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ password }),
      });
      if (!response.ok) throw new Error("LINK_INVALIDO_OU_EXPIRADO");

      form.hidden = true;
      message.textContent = "Senha atualizada. Você já pode entrar no painel.";
      const link = document.createElement("a");
      link.href = `${browserWindow.location.origin}/`;
      link.textContent = "Voltar para o login";
      message.appendChild(document.createElement("br"));
      message.appendChild(link);
    } catch (error) {
      message.textContent =
        error.message === "LINK_INVALIDO_OU_EXPIRADO"
          ? "O link expirou ou não é válido. Solicite um novo link."
          : "Não foi possível atualizar a senha. Tente novamente.";
      submit.disabled = false;
    }
  });
})();
