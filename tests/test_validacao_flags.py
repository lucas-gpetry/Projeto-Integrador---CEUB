"""Testes da auditoria das flags e do padrão-ouro. Todo o texto aqui é sintético."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import spacy
from openpyxl import load_workbook

from src.clean_data import limpar_historico
from src.utils import auditoria_flags as af
from src.utils import padrao_ouro as po
from src.utils.nlp_engines import gatilhos_adicionais, gatilhos_regex, gatilhos_tipos, normalizar_para_nlp

NLP = spacy.load("pt_core_news_sm", disable=["ner", "textcat"])


def registro(texto):
    return af.analisar_documento(NLP(normalizar_para_nlp(texto)), limpar_historico(texto))


def predicoes_sinteticas(n=2000, semente=1):
    rng = np.random.default_rng(semente)
    taxas = np.linspace(0.005, 0.4, len(po.FLAGS))
    return pd.DataFrame({flag: rng.random(n) < taxa for flag, taxa in zip(po.FLAGS, taxas)})


class TestGatilhos(unittest.TestCase):
    def test_regex_informa_o_termo(self):
        self.assertIn(("flag_arma_branca", "faca"), list(gatilhos_regex("o autor pegou uma faca")))

    def test_regex_ignora_mencao_negada(self):
        self.assertNotIn("flag_arma_branca", {f for f, _ in gatilhos_regex("o autor nao portava faca")})

    def test_tipos_informa_o_lema(self):
        doc = NLP(normalizar_para_nlp("O autor deu um soco na vítima."))
        self.assertIn(("v_fisica", "soco"), list(gatilhos_tipos(doc)))

    def test_desfecho_aparece_como_gatilho(self):
        doc = NLP(normalizar_para_nlp("As partes foram levadas para a delegacia."))
        self.assertIn(("desfecho_dp", "delegacia"), list(gatilhos_adicionais(doc)))


class TestAuditoria(unittest.TestCase):
    def test_candidato_fora_do_dicionario(self):
        achados = af.candidatos_ampliados(limpar_historico("A vítima foi esganada pelo autor."))
        self.assertIn("estrangulamento", achados["v_fisica"])

    def test_candidato_negado_nao_conta(self):
        achados = af.candidatos_ampliados(limpar_historico("A vítima não foi esganada."))
        self.assertNotIn("v_fisica", achados)

    def test_improcedencia_zera_a_forma_mas_mantem_o_gatilho(self):
        r = registro("O autor deu um soco na vítima. Nada constatado.")
        self.assertIn("v_fisica", r["gatilhos"])
        self.assertFalse(af.flag_positiva(r, "v_fisica"))

    def test_de_acordo_com_sai_no_cenario(self):
        r = {"gatilhos": {"desfecho_local": {"acordo"}}, "acordo_idiomatico": True, "orientou_delegacia": False, "encaminhou_saude": False}
        self.assertEqual(af.desfecho(r), "resolvido_local")
        self.assertEqual(af.desfecho(r, "sem_de_acordo"), "nao_identificado")

    def test_detecta_de_acordo_com_no_texto(self):
        self.assertTrue(registro("De acordo com a vítima, houve briga.")["acordo_idiomatico"])
        self.assertFalse(registro("As partes fizeram um acordo.")["acordo_idiomatico"])

    def test_orientar_a_procurar_delegacia_nao_e_conducao(self):
        r = {"gatilhos": {"desfecho_dp": {"delegacia"}, "desfecho_local": {"orientar"}}, "acordo_idiomatico": True, "orientou_delegacia": True, "encaminhou_saude": False}
        self.assertEqual(af.desfecho(r), "encaminhado_dp")
        self.assertEqual(af.desfecho(r, "orientacao_nao_conduz"), "resolvido_local")

    def test_termos_e_faixas(self):
        base = {"improcedente": False, "candidatos": {}, "palavras": 10}
        registros = [
            {**base, "gatilhos": {"v_psicologica": {"medo"}}},
            {**base, "gatilhos": {"v_psicologica": {"medo", "ameacar"}}},
            {**base, "gatilhos": {}, "candidatos": {"v_psicologica": {"radical: ameac-"}}},
            {**base, "gatilhos": {}, "candidatos": {"v_psicologica": {"perturbacao"}}},
        ]
        termos = af.resumir_termos(registros).set_index("termo")
        self.assertEqual(termos.loc["medo", "historicos"], 2)
        self.assertEqual(termos.loc["medo", "unico_sustento"], 1)
        self.assertAlmostEqual(termos.loc["medo", "prevalencia_sem_o_termo"], 0.25)
        faixa = af.faixas_por_flag(registros).set_index("flag").loc["v_psicologica"]
        self.assertEqual(faixa["so_termos_ambiguos"], 1)
        self.assertEqual(faixa["radical_nao_reconhecido"], 1)
        self.assertEqual(faixa["mencao_fora_do_dicionario"], 1)
        self.assertAlmostEqual(faixa["cobertura_pior_cenario"], 0.5)

    def test_razoes_mudam_com_o_cenario(self):
        base = {"improcedente": False, "candidatos": {}, "acordo_idiomatico": False, "orientou_delegacia": False, "encaminhou_saude": False}
        registros = []
        for i in range(40):
            gatilhos = {"desfecho_dp": {"conduzir"}} if i < 20 else {"desfecho_local": {"resolver" if i < 30 else "orientar"}}
            if i < 15 or 30 <= i < 33:
                gatilhos["v_fisica"] = {"soco"}
            registros.append({**base, "gatilhos": gatilhos, "palavras": 10 + i})
        tabela = af.razoes_por_cenario(registros, formas=("v_fisica",)).set_index("cenario")
        self.assertEqual(tabela.loc["observado", "resolvidos"], 20)
        self.assertEqual(tabela.loc["sem_resolver", "resolvidos"], 10)
        self.assertEqual(tabela.loc["observado", "encaminhados"], 20)

    def test_supressao(self):
        tabela = af.suprimir_contagens(pd.DataFrame({"n": [0, 3, 5]}), ["n"])
        self.assertEqual(tabela["n"].tolist(), [0, "<5", 5])


class TestAmostra(unittest.TestCase):
    def test_estrato_e_a_flag_mais_rara(self):
        linhas = [{f: False for f in po.FLAGS} for _ in range(5)]
        for linha in linhas[:4]:
            linha["v_fisica"] = True
        linhas[0]["v_sexual"] = True
        estratos = po.atribuir_estratos(pd.DataFrame(linhas))
        self.assertEqual(estratos.tolist(), ["v_sexual", "v_fisica", "v_fisica", "v_fisica", "nenhuma_flag"])

    def test_alocacao_fecha_o_total_e_respeita_limites(self):
        tamanhos = pd.Series({"a": 5, "b": 100, "c": 5000})
        n = po.alocar_estratos(tamanhos, 100, pisos=10)
        self.assertEqual(n.sum(), 100)
        self.assertEqual(n["a"], 5)
        self.assertGreaterEqual(n["b"], 10)

    def test_flag_rara_recebe_piso_maior(self):
        pred = predicoes_sinteticas(n=20000)
        amostra = po.sortear_amostra(pred, 300)
        por_estrato = amostra["estrato"].value_counts()
        self.assertGreaterEqual(por_estrato[po.FLAGS[0]], po.PISO_RARO)
        self.assertGreaterEqual(por_estrato["nenhuma_flag"], po.PISO_SEM_FLAG)

    def test_amostra_reprodutivel_com_pesos_corretos(self):
        pred = predicoes_sinteticas()
        a, b = po.sortear_amostra(pred, 300), po.sortear_amostra(pred, 300)
        pd.testing.assert_frame_equal(a, b)
        self.assertEqual(a["indice_base"].nunique(), 300)
        self.assertAlmostEqual(a["peso"].sum(), len(pred))

    def test_pares_equilibrados(self):
        amostra = po.distribuir_pares(po.sortear_amostra(predicoes_sinteticas(), 300))
        self.assertTrue((amostra["anotador_1"] != amostra["anotador_2"]).all())
        self.assertEqual(amostra.groupby(["anotador_1", "anotador_2"]).size().tolist(), [30] * 10)
        for anotador in po.ANOTADORES:
            self.assertEqual(int((amostra["anotador_1"].eq(anotador) | amostra["anotador_2"].eq(anotador)).sum()), 120)
        self.assertEqual(amostra["id_amostra"].nunique(), 300)

    def test_saida_precisa_estar_ignorada(self):
        self.assertTrue(po.saida_ignorada_pelo_git("outputs/padrao_ouro"))
        self.assertFalse(po.saida_ignorada_pelo_git("docs"))


class TestMetricas(unittest.TestCase):
    def test_kappa_valor_conhecido(self):
        self.assertAlmostEqual(po.kappa_cohen([1, 1, 0, 0], [1, 0, 0, 0]), 0.5)

    def test_kappa_multiclasse_acordo_total(self):
        self.assertAlmostEqual(po.kappa_cohen(["a", "b", "c"], ["a", "b", "c"]), 1.0)

    def test_tamanho_efetivo(self):
        self.assertAlmostEqual(po.tamanho_efetivo([1, 1, 1, 1]), 4.0)
        self.assertAlmostEqual(po.tamanho_efetivo([3, 1]), 16 / 10)

    def test_metricas_usam_os_pesos(self):
        predito = [True, True, False, False]
        ouro = [True, False, True, False]
        m = po.metricas_flag(predito, ouro, [1.0, 3.0, 4.0, 2.0])
        self.assertAlmostEqual(m["precisao"], 0.25)
        self.assertAlmostEqual(m["recall"], 0.2)
        self.assertAlmostEqual(m["f1"], 2 / 9)
        self.assertAlmostEqual(m["prevalencia_ouro"], 0.5)
        self.assertAlmostEqual(m["prevalencia_regra"], 0.4)
        self.assertLess(m["precisao_inf"], 0.25)
        self.assertGreater(m["precisao_sup"], 0.25)

    def test_flag_sem_positivo_nao_quebra(self):
        m = po.metricas_flag([False, False], [False, False], [1.0, 1.0])
        self.assertTrue(np.isnan(m["precisao"]))

    def test_bootstrap_reprodutivel_e_contem_o_f1(self):
        rng = np.random.default_rng(3)
        ouro = rng.random(200) < 0.4
        predito = np.where(rng.random(200) < 0.9, ouro, ~ouro)
        pesos, estratos = np.ones(200), np.array(["a", "b"] * 100)
        ic = po.ic_f1_bootstrap(predito, ouro, pesos, estratos, repeticoes=200)
        self.assertEqual(ic, po.ic_f1_bootstrap(predito, ouro, pesos, estratos, repeticoes=200))
        self.assertTrue(ic[0] <= po._f1(predito, ouro, pesos) <= ic[1])


class TestConsolidacao(unittest.TestCase):
    def longo(self):
        return pd.DataFrame([
            {"id_amostra": "N1", "coluna": "v_fisica", "anotador": "A", "rotulo": "sim"},
            {"id_amostra": "N1", "coluna": "v_fisica", "anotador": "B", "rotulo": "sim"},
            {"id_amostra": "N2", "coluna": "v_fisica", "anotador": "A", "rotulo": "sim"},
            {"id_amostra": "N2", "coluna": "v_fisica", "anotador": "B", "rotulo": "nao"},
            {"id_amostra": "N1", "coluna": "nao_avaliavel", "anotador": "A", "rotulo": ""},
            {"id_amostra": "N1", "coluna": "nao_avaliavel", "anotador": "B", "rotulo": ""},
            {"id_amostra": "N2", "coluna": "nao_avaliavel", "anotador": "A", "rotulo": ""},
            {"id_amostra": "N2", "coluna": "nao_avaliavel", "anotador": "B", "rotulo": ""},
        ])

    def test_divergencia_fica_pendente(self):
        ouro, pendencias = po.consolidar(self.longo())
        self.assertEqual(ouro.loc["N1", "v_fisica"], "sim")
        self.assertEqual(pendencias["id_amostra"].tolist(), ["N2"])

    def test_adjudicacao_resolve(self):
        decisao = pd.DataFrame([{"id_amostra": "N2", "coluna": "v_fisica", "rotulo_final": "nao"}])
        ouro, pendencias = po.consolidar(self.longo(), decisao)
        self.assertEqual(ouro.loc["N2", "v_fisica"], "nao")
        self.assertTrue(pendencias.empty)

    def test_nao_avaliavel_dispensa_as_demais_colunas(self):
        longo = pd.DataFrame([
            {"id_amostra": "N1", "coluna": "nao_avaliavel", "anotador": "A", "rotulo": "sim"},
            {"id_amostra": "N1", "coluna": "nao_avaliavel", "anotador": "B", "rotulo": "sim"},
            {"id_amostra": "N1", "coluna": "v_fisica", "anotador": "A", "rotulo": ""},
            {"id_amostra": "N1", "coluna": "v_fisica", "anotador": "B", "rotulo": ""},
        ])
        self.assertEqual(po.conferir_preenchimento(longo).sum(), 0)
        ouro, pendencias = po.consolidar(longo)
        self.assertEqual(ouro.loc["N1", "nao_avaliavel"], "sim")
        self.assertTrue(pendencias.empty)

    def test_preenchimento_acusa_branco(self):
        longo = self.longo()
        longo.loc[0, "rotulo"] = ""
        self.assertEqual(po.conferir_preenchimento(longo).to_dict(), {"A": 1, "B": 0})


class TestPlanilhas(unittest.TestCase):
    def test_ida_e_volta(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "anotador_A.xlsx"
            po.gravar_planilha_anotador(caminho, [("N001", "=1+1 texto sintético"), ("N002", "controle\x01 sintético")])
            planilha = load_workbook(caminho)
            aba = planilha["Rotulos"]
            self.assertEqual(aba["B2"].data_type, "s")
            self.assertNotIn("\x01", aba["B3"].value)
            self.assertEqual(planilha.sheetnames, ["Guia", "Rotulos"])
            self.assertNotIn("v_fisica", [c.value for c in aba[1]])
            aba["C2"] = "sim"
            aba["P2"] = "resolvido_local"
            aba["R2"] = "comentário sintético"
            planilha.save(caminho)
            longo = po.ler_planilha_anotador(caminho, "A")
            self.assertEqual(longo.query("id_amostra == 'N001' and coluna == 'v_fisica'")["rotulo"].item(), "sim")
            self.assertEqual(longo.query("id_amostra == 'N001' and coluna == 'desfecho'")["rotulo"].item(), "resolvido_local")
            self.assertNotIn("historico", longo.columns)
            self.assertFalse(longo["rotulo"].str.contains("sintético").any())

    def test_valor_invalido_e_rejeitado(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "anotador_A.xlsx"
            po.gravar_planilha_anotador(caminho, [("N001", "texto sintético")])
            planilha = load_workbook(caminho)
            planilha["Rotulos"]["C2"] = "talvez"
            planilha.save(caminho)
            with self.assertRaises(ValueError):
                po.ler_planilha_anotador(caminho, "A")


class TestFluxoCompleto(unittest.TestCase):
    def test_avaliacao_recupera_o_erro_conhecido(self):
        pred = predicoes_sinteticas()
        amostra = po.distribuir_pares(po.sortear_amostra(pred, 300))
        desfecho = pd.Series("encaminhado_dp", index=pred.index, name="desfecho")
        gabarito = amostra.join(pred, on="indice_base").join(desfecho, on="indice_base")
        registros = []
        for r in gabarito.itertuples():
            for anotador in (r.anotador_1, r.anotador_2):
                for flag in po.FLAGS:
                    valor = getattr(r, flag)
                    # O padrão-ouro discorda da regra em toda predição positiva de v_fisica.
                    if flag == "v_fisica":
                        valor = False
                    registros.append({"id_amostra": r.id_amostra, "coluna": flag, "anotador": anotador, "rotulo": "sim" if valor else "nao"})
                registros.append({"id_amostra": r.id_amostra, "coluna": "desfecho", "anotador": anotador, "rotulo": r.desfecho})
                registros.append({"id_amostra": r.id_amostra, "coluna": "nao_avaliavel", "anotador": anotador, "rotulo": ""})
        ouro, pendencias = po.consolidar(pd.DataFrame(registros))
        self.assertTrue(pendencias.empty)
        metricas = po.avaliar_flags(gabarito, ouro).set_index("flag")
        self.assertEqual(metricas.loc["v_fisica", "precisao"], 0.0)
        self.assertAlmostEqual(metricas.loc["flag_filhos", "precisao"], 1.0)
        self.assertAlmostEqual(metricas.loc["flag_filhos", "recall"], 1.0)
        self.assertAlmostEqual(metricas.loc["flag_filhos", "prevalencia_regra"], pred["flag_filhos"].mean(), delta=0.1)
        matriz = po.matriz_desfecho(gabarito, ouro)
        self.assertAlmostEqual(matriz.to_numpy().sum(), len(pred))


if __name__ == "__main__":
    unittest.main()
