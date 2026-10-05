import unittest
from unittest.mock import Mock, patch

import administracao


class TestAdministracaoTenant(unittest.TestCase):
    @patch("administracao.eh_owner_tenant", return_value=False)
    def test_listar_tenants_administrados_retorna_vazio_sem_owner(self, _: Mock) -> None:
        self.assertEqual(administracao.listar_tenants_administrados(), [])

    @patch("administracao.eh_owner_tenant", return_value=True)
    @patch("administracao.obter_cliente_supabase")
    @patch("administracao.st.session_state", {"_mi_supabase_user_id": "user-123"})
    def test_listar_tenants_administrados_leia_membrasia_owner(
        self,
        cliente_mock: Mock,
        _: Mock,
    ) -> None:
        cliente_mock.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"tenant_id": "tenant-1", "role": "owner"}
        ]

        self.assertEqual(administracao.listar_tenants_administrados(), [{"tenant_id": "tenant-1", "role": "owner"}])

    @patch("administracao.eh_owner_tenant", return_value=False)
    def test_exigir_permissao_admin_tenant_rejeita_sem_owner(self, _: Mock) -> None:
        with self.assertRaisesRegex(RuntimeError, "Acesso administrativo"):
            administracao.exigir_permissao_admin_tenant()

    @patch("administracao.obter_cliente_supabase")
    @patch("administracao.st.session_state", {"_mi_supabase_user_id": "user-123"})
    def test_solicitar_onboarding_piloto_registra_acoes_sem_tenant(
        self,
        cliente_mock: Mock,
    ) -> None:
        consulta = cliente_mock.return_value.table.return_value.select.return_value
        consulta.eq.return_value = consulta
        consulta.is_.return_value = consulta
        consulta.order.return_value = consulta
        consulta.limit.return_value.execute.return_value.data = []
        cliente_mock.return_value.table.return_value.insert.return_value.execute.return_value.data = [
            {
                "actor_user_id": "user-123",
                "actor_tenant_id": None,
                "action": "pilot_onboarding_request",
                "target_tenant_id": None,
                "reason": "Solicito acesso ao piloto",
            }
        ]

        evento = administracao.solicitar_onboarding_piloto(motivo="Solicito acesso ao piloto")

        self.assertEqual(evento["action"], "pilot_onboarding_request")
        self.assertIsNone(evento["actor_tenant_id"])
        self.assertIsNone(evento["target_tenant_id"])

    @patch("administracao.obter_cliente_supabase")
    @patch("administracao.st.session_state", {"_mi_supabase_user_id": "user-123"})
    def test_solicitar_onboarding_piloto_reaproveita_pedido_pendente(
        self,
        cliente_mock: Mock,
    ) -> None:
        consulta = cliente_mock.return_value.table.return_value.select.return_value
        consulta.eq.return_value = consulta
        consulta.is_.return_value = consulta
        consulta.order.return_value = consulta
        consulta.limit.return_value.execute.return_value.data = [
            {
                "actor_user_id": "user-123",
                "actor_tenant_id": None,
                "target_tenant_id": None,
                "action": "pilot_onboarding_request",
                "reason": "Solicito acesso ao piloto",
            }
        ]

        evento = administracao.solicitar_onboarding_piloto(motivo="Solicito acesso ao piloto")

        self.assertEqual(evento["action"], "pilot_onboarding_request")
        self.assertIsNone(evento["actor_tenant_id"])

    @patch("administracao.exigir_administrador_piloto")
    @patch("administracao.obter_cliente_supabase")
    def test_listar_solicitacoes_pendentes_filtra_apenas_pedidos_sem_destino(
        self,
        cliente_mock: Mock,
        _: Mock,
    ) -> None:
        consulta = cliente_mock.return_value.table.return_value.select.return_value
        consulta.eq.return_value = consulta
        consulta.is_.return_value = consulta
        consulta.order.return_value.execute.return_value.data = [
            {
                "actor_user_id": "user-456",
                "actor_tenant_id": None,
                "target_tenant_id": None,
                "action": "pilot_onboarding_request",
            }
        ]

        solicitacoes = administracao.listar_solicitacoes_piloto_pendentes()

        self.assertEqual(len(solicitacoes), 1)
        consulta.eq.assert_called_once_with("action", "pilot_onboarding_request")
        self.assertEqual(consulta.is_.call_args_list[0].args, ("actor_tenant_id", "null"))
        self.assertEqual(consulta.is_.call_args_list[1].args, ("target_tenant_id", "null"))

    @patch("administracao.eh_administrador_piloto", return_value=True)
    @patch("administracao.obter_cliente_supabase")
    @patch("administracao.obter_tenant_id", return_value="owner-tenant-1")
    @patch("administracao.st.session_state", {"_mi_supabase_user_id": "owner-123"})
    def test_aprovar_onboarding_piloto_cria_tenant_e_vinculo(
        self,
        tenant_id_mock: Mock,
        cliente_mock: Mock,
        admin_mock: Mock,
    ) -> None:
        cliente_mock.return_value.rpc.return_value.execute.return_value.data = {
            "tenant_id": "tenant-approve-1",
            "user_id": "user-456",
            "role": "member",
            "request_id": "request-1",
        }

        evento = administracao.aprovar_onboarding_piloto(
            user_id="user-456",
            nome_tenant="Tenant do piloto A",
            papel="member",
        )

        self.assertEqual(evento["tenant_id"], "tenant-approve-1")
        self.assertEqual(evento["user_id"], "user-456")
        self.assertEqual(evento["role"], "member")
        cliente_mock.return_value.rpc.assert_called_once_with(
            "approve_pilot_onboarding",
            {
                "p_user_id": "user-456",
                "p_tenant_name": "Tenant do piloto A",
                "p_role": "member",
                "p_actor_tenant_id": "owner-tenant-1",
                "p_target_tenant_id": None,
            },
        )

    @patch("administracao.eh_owner_tenant", return_value=True)
    @patch("administracao.obter_cliente_supabase")
    @patch("administracao.obter_tenant_id", return_value="tenant-1")
    @patch("administracao.st.session_state", {"_mi_supabase_user_id": "user-123"})
    def test_registrar_auditoria_acesso_inclui_payload_esperado(
        self,
        tenant_id_mock: Mock,
        cliente_mock: Mock,
        _: Mock,
    ) -> None:
        cliente_mock.return_value.table.return_value.insert.return_value.execute.return_value.data = [
            {
                "actor_user_id": "user-123",
                "actor_tenant_id": "tenant-1",
                "action": "view",
                "target_tenant_id": "tenant-2",
                "reason": "Revisão de acesso",
            }
        ]

        evento = administracao.registrar_auditoria_acesso(
            acao="view",
            target_tenant_id="tenant-2",
            motivo="Revisão de acesso",
        )

        self.assertEqual(evento["actor_tenant_id"], "tenant-1")
        self.assertEqual(evento["target_tenant_id"], "tenant-2")

    @patch("administracao.eh_owner_tenant", return_value=True)
    @patch("administracao.obter_cliente_supabase")
    @patch("administracao.obter_tenant_id", return_value="tenant-1")
    @patch("administracao.st.session_state", {"_mi_supabase_user_id": "user-123"})
    def test_listar_membros_tenant_retorna_membros_do_tenant(
        self,
        tenant_id_mock: Mock,
        cliente_mock: Mock,
        _: Mock,
    ) -> None:
        cliente_mock.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
            {"user_id": "user-123", "tenant_id": "tenant-1", "role": "owner", "created_at": "2026-01-01T00:00:00Z"}
        ]

        self.assertEqual(
            administracao.listar_membros_tenant(),
            [{"user_id": "user-123", "tenant_id": "tenant-1", "role": "owner", "created_at": "2026-01-01T00:00:00Z"}],
        )

    @patch("administracao.eh_owner_tenant", return_value=True)
    @patch("administracao.listar_membros_tenant", return_value=[{"user_id": "user-123", "role": "owner"}])
    @patch("administracao.listar_auditoria_acesso", return_value=[{"action": "view", "actor_user_id": "user-123", "target_tenant_id": "tenant-2", "reason": "Revisão", "created_at": "2026-01-01T00:00:00Z"}])
    @patch("administracao.obter_tenant_id", return_value="tenant-1")
    @patch("administracao.st.dataframe")
    @patch("administracao.st.info")
    @patch("administracao.st.caption")
    @patch("administracao.st.subheader")
    @patch("administracao.listar_solicitacoes_piloto_pendentes", return_value=[])
    @patch("administracao.eh_administrador_piloto", return_value=True)
    def test_mostrar_painel_administracao_renderiza_sem_erros(
        self,
        _admin: Mock,
        _solicitacoes: Mock,
        _subheader: Mock,
        _caption: Mock,
        _info: Mock,
        _dataframe: Mock,
        _tenant_id: Mock,
        _auditoria: Mock,
        _membros: Mock,
        _owner: Mock,
    ) -> None:
        administracao.mostrar_painel_administracao()
        self.assertTrue(_dataframe.called)


if __name__ == "__main__":
    unittest.main()
