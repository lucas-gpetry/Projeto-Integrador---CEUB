"""Testes da associação entre categorias e formas de violência.

Executar a partir da raiz do projeto: python -m unittest discover -s tests
"""

import unittest

import numpy as np
import pandas as pd

from src.utils import associacao_formas as af


class TestRespostasValidas(unittest.TestCase):
    def test_codigos_sinan_excluem_ignorado_e_vazio(self):
        df = pd.DataFrame({"f": ["1", "2", "9", "", "1"]})
        v = af.respostas_validas(df, "f")
        self.assertEqual(len(v), 3)
        self.assertEqual(int(v["_sim"].sum()), 2)

    def test_flag_booleana_mantem_todos_os_registros(self):
        v = af.respostas_validas(pd.DataFrame({"f": [True, False, False]}), "f")
        self.assertEqual(len(v), 3)


class TestAssociacao(unittest.TestCase):
    def test_associacao_perfeita_tem_v_igual_a_um(self):
        df = pd.DataFrame({"cat": ["a"] * 10 + ["b"] * 10 + ["c"] * 10, "f": [True] * 10 + [False] * 20})
        r = af.associacao(df, "cat", "f")
        self.assertAlmostEqual(r["v_cramer"], 1.0)
        self.assertEqual((r["n"], r["casos"]), (30, 10))

    def test_independencia_tem_v_zero_e_conta_esperado_baixo(self):
        df = pd.DataFrame({"cat": ["a"] * 4 + ["b"] * 4 + ["c"] * 4, "f": [True, False] * 6})
        r = af.associacao(df, "cat", "f")
        self.assertAlmostEqual(r["v_cramer"], 0.0)
        self.assertEqual(r["esperado_min"], 2.0)
        self.assertEqual(r["pct_esperado_menor_5"], 1.0)

    def test_ignorado_fica_fora_do_teste(self):
        df = pd.DataFrame({"cat": list("aabbcc") + ["c"], "f": ["1", "1", "2", "2", "2", "2", "9"]})
        self.assertEqual(af.associacao(df, "cat", "f")["n"], 6)

    def test_spearman_de_flag_monotonica(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4], "f": [False, False, True, True]})
        self.assertAlmostEqual(af.spearman(df, "x", "f")["rho"], 2 / np.sqrt(5))

    def test_spearman_nao_ve_relacao_em_u(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5, 6], "f": [True, False, False, False, False, True]})
        self.assertAlmostEqual(af.spearman(df, "x", "f")["rho"], 0.0)

    def test_razoes_bruta_e_ajustada(self):
        df = pd.DataFrame({
            "e": [True] * 4 + [False] * 4 + [True] * 4 + [False] * 4,
            "f": [True, True, False, False, True, False, False, False] * 2,
            "s": [0] * 8 + [1] * 8,
        })
        r = af.razoes(df, "e", "f", "s")
        self.assertAlmostEqual(r["bruta_rp"], 2.0)
        self.assertAlmostEqual(r["ajustada_rp"], 2.0)

    def test_razao_fica_vazia_com_contagem_abaixo_de_k(self):
        df = pd.DataFrame({
            "e": [True] * 20 + [False] * 20,
            "f": [True] * 3 + [False] * 17 + [True] * 10 + [False] * 10,
            "s": 0,
        })
        self.assertTrue(np.isnan(af.razoes(df, "e", "f", "s", k=5)["ajustada_rp"]))
        self.assertFalse(np.isnan(af.razoes(df, "e", "f", "s", k=3)["ajustada_rp"]))

    def test_tabela_tem_uma_linha_por_forma_e_so_o_que_foi_pedido(self):
        df = pd.DataFrame({"cat": list("aabbcc") * 3, "f1": [True, False] * 9, "f2": [False, True] * 9})
        t = af.tabela_associacoes(df, "cat", {"f1": "Um", "f2": "Dois"})
        self.assertEqual(t["rotulo"].tolist(), ["Um", "Dois"])
        self.assertNotIn("rho", t)
        self.assertNotIn("ajustada_rp", t)


class TestFamiliaDeTestes(unittest.TestCase):
    def test_ajuste_usa_todos_os_p_valores_como_uma_familia(self):
        def dobra(p):
            self.assertEqual(len(p), 3)
            return p * 2

        tabelas = {
            "a": pd.DataFrame({"coluna": ["x"], "p": [0.01], "p_rho": [0.02]}),
            "b": pd.DataFrame({"coluna": ["x"], "p": [0.03]}),
        }
        saida = af.ajustar_familia(tabelas, dobra)
        self.assertAlmostEqual(saida["a"]["p_bh"].iat[0], 0.02)
        self.assertAlmostEqual(saida["a"]["p_rho_bh"].iat[0], 0.04)
        self.assertAlmostEqual(saida["b"]["p_bh"].iat[0], 0.06)
        self.assertNotIn("p_rho_bh", saida["b"])


class TestSupressao(unittest.TestCase):
    @staticmethod
    def _base(casos_por_categoria, n=20):
        linhas = []
        for categoria, casos in casos_por_categoria.items():
            linhas += [{"cat": categoria, "f": i < casos} for i in range(n)]
        return pd.DataFrame(linhas)

    def test_sem_contagem_pequena_nada_e_suprimido(self):
        t = af.percentuais(self._base({"a": 10, "b": 8}), "cat", {"f": "F"}, k=5)
        self.assertFalse(t["suprimido"].any())
        self.assertAlmostEqual(t.set_index("categoria").loc["a", "p"], 0.5)

    def test_celula_unica_leva_a_segunda_menor_junto(self):
        t = af.percentuais(self._base({"a": 3, "b": 8, "c": 12}), "cat", {"f": "F"}, k=5).set_index("categoria")
        self.assertTrue(t.loc["a", "suprimido"])
        self.assertTrue(t.loc["b", "suprimido"])
        self.assertFalse(t.loc["c", "suprimido"])
        self.assertTrue(np.isnan(t.loc["a", "p"]))
        self.assertTrue(np.isnan(t.loc["b", "casos"]))

    def test_complemento_pequeno_tambem_e_suprimido(self):
        t = af.percentuais(self._base({"a": 18, "b": 9, "c": 10}), "cat", {"f": "F"}, k=5).set_index("categoria")
        self.assertTrue(t.loc["a", "suprimido"])

    def test_zero_casos_nao_e_suprimido(self):
        t = af.percentuais(self._base({"a": 0, "b": 9, "c": 10}), "cat", {"f": "F"}, k=5).set_index("categoria")
        self.assertFalse(t["suprimido"].any())
        self.assertEqual(t.loc["a", "p"], 0.0)


class TestComposicao(unittest.TestCase):
    def test_denominadores_e_uniao_de_flags(self):
        pmdf = pd.DataFrame({"v_psi": [True, False, False, False], "v_mor": [False, True, False, False]})
        sinan = pd.DataFrame({"VIOL": ["1"] * 6 + ["2"] * 4 + ["9"] * 2})
        t = af.composicao_fontes(pmdf, {"total": sinan}, [("Psic. ou moral", ["v_psi", "v_mor"], "VIOL")], k=2).iloc[0]
        self.assertAlmostEqual(t["pmdf_p"], 0.5)
        self.assertAlmostEqual(t["total_p"], 0.6)
        self.assertEqual((t["total_n"], t["total_ignorado"]), (10, 2))

    def test_contagem_pequena_fica_vazia(self):
        pmdf = pd.DataFrame({"f": [True] + [False] * 9})
        sinan = pd.DataFrame({"VIOL": ["1"] * 2 + ["2"] * 8})
        t = af.composicao_fontes(pmdf, {"total": sinan}, [("X", ["f"], "VIOL")], k=5).iloc[0]
        self.assertTrue(np.isnan(t["pmdf_p"]))
        self.assertTrue(np.isnan(t["total_p"]))


class TestImprocedencia(unittest.TestCase):
    def test_ignora_caixa_e_acento(self):
        textos = pd.Series(["Nada CONSTATADO no local", "sem termo", None, "ausência de marcas"])
        self.assertEqual(af.narrativa_improcedente(textos, ["nada constatado", "ausencia"]).tolist(), [True, False, False, True])


if __name__ == "__main__":
    unittest.main()
