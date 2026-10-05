import unittest
from unittest.mock import Mock, patch

import autenticacao


class TestAutenticacaoTenant(unittest.TestCase):
    @patch("autenticacao.st.session_state", {"_mi_tenant_role": "owner"})
    def test_eh_owner_tenant_reconhece_owner(self) -> None:
        self.assertTrue(autenticacao.eh_owner_tenant())

    @patch("autenticacao.st.session_state", {"_mi_tenant_role": "member"})
    def test_eh_owner_tenant_rejeita_member(self) -> None:
        self.assertFalse(autenticacao.eh_owner_tenant())

    @patch("autenticacao.st.session_state", {"_mi_tenant_role": "member"})
    def test_exigir_permissao_administrativa_rejeita_sem_owner(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Acesso administrativo"):
            autenticacao.exigir_permissao_administrativa()

    @patch("autenticacao.st.session_state", {"_mi_tenant_role": "owner"})
    def test_exigir_permissao_administrativa_permite_owner(self) -> None:
        autenticacao.exigir_permissao_administrativa()


if __name__ == "__main__":
    unittest.main()
