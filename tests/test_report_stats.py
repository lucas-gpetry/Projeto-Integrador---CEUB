"""Testes das estatísticas do relatório analítico com casos de resultado conhecido.

Executar a partir da raiz do projeto: python -m unittest discover -s tests
"""

import unittest
from datetime import date

import numpy as np
import pandas as pd

from src.utils import report_stats as rs


def tabela_2x2(a, n1, c, n0, estrato=0):
    """Registros com exposição/desfecho que reproduzem uma tabela 2x2."""
    exp = [True] * n1 + [False] * n0
    out = [True] * a + [False] * (n1 - a) + [True] * c + [False] * (n0 - c)
    return pd.DataFrame({"exp": exp, "out": out, "estrato": estrato})


class TestProporcoes(unittest.TestCase):
    def test_wilson_valores_de_referencia(self):
        p, lo, hi = rs.wilson_ci(5, 10)
        self.assertAlmostEqual(p, 0.5)
        self.assertAlmostEqual(lo, 0.2366, places=4)
        self.assertAlmostEqual(hi, 0.7634, places=4)
        _, lo0, hi0 = rs.wilson_ci(0, 10)
        self.assertAlmostEqual(lo0, 0.0, places=10)
        self.assertAlmostEqual(hi0, 0.2775, places=4)

    def test_razao_prevalencia_bruta(self):
        r = rs.razao_prevalencia(tabela_2x2(20, 100, 10, 100), "exp", "out")
        self.assertAlmostEqual(r["rp"], 2.0)
        ep = np.sqrt(1 / 20 - 1 / 100 + 1 / 10 - 1 / 100)
        self.assertAlmostEqual(r["ic_inf"], 2.0 * np.exp(-1.96 * ep))
        self.assertAlmostEqual(r["ic_sup"], 2.0 * np.exp(1.96 * ep))

    def test_mantel_haenszel_remove_confundimento(self):
        # RP = 2 dentro de cada estrato; a bruta é inflada porque os expostos se concentram no estrato de risco alto.
        df = pd.concat([tabela_2x2(40, 100, 2, 10, estrato=0), tabela_2x2(1, 10, 5, 100, estrato=1)])
        self.assertGreater(rs.razao_prevalencia(df, "exp", "out")["rp"], 5)
        r = rs.razao_prevalencia_mh(df, "exp", "out", "estrato")
        self.assertAlmostEqual(r["rp"], 2.0)
        self.assertLess(r["ic_inf"], 2.0)
        self.assertGreater(r["ic_sup"], 2.0)

    def test_mantel_haenszel_com_um_estrato_igual_a_bruta(self):
        df = tabela_2x2(20, 100, 10, 100)
        self.assertAlmostEqual(rs.razao_prevalencia_mh(df, "exp", "out", "estrato")["rp"],
                               rs.razao_prevalencia(df, "exp", "out")["rp"])


class TestCalendario(unittest.TestCase):
    def test_lacunas_de_registro(self):
        dias = pd.Series(pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-06", "2024-01-08"]))
        # 03 a 05/01 é lacuna (3 dias); 07/01 sozinho fica abaixo do mínimo de 2 dias.
        self.assertEqual(rs.lacunas_de_registro(dias), [(date(2024, 1, 3), date(2024, 1, 5), 3)])

    def test_dias_da_semana_em_2024(self):
        datas = pd.Series(pd.date_range("2024-01-01", "2024-12-31"))
        tabela, teste = rs.distribuicao_calendario(datas, "dia_semana")
        self.assertEqual(tabela["dias"].tolist(), [53, 53, 52, 52, 52, 52, 52])
        # Um registro por dia: observado igual ao esperado.
        self.assertAlmostEqual(teste["qui2"], 0.0)

    def test_efeito_datas_e_exclusao(self):
        dias = pd.date_range("2024-01-01", "2024-03-31")
        contagem = pd.Series(10, index=dias)
        contagem[pd.Timestamp("2024-02-14")] = 20
        datas = pd.Series(np.repeat(dias.values, contagem.values))
        especiais = {date(2024, 2, 14): "Teste", date(2024, 3, 6): "Excluída"}
        tabela, ef = rs.efeito_datas(datas, especiais, dias_excluidos=[pd.Timestamp("2024-03-06")])
        self.assertEqual(tabela.set_index("nome").loc["Excluída", "excluida"], True)
        self.assertEqual(ef["observado"], 20)
        self.assertAlmostEqual(ef["razao"], 2.0)
        self.assertLess(ef["ic_inf"], 2.0)
        self.assertGreater(ef["ic_sup"], 2.0)

    def test_razao_taxas(self):
        r = rs.razao_taxas(100, 10, 50, 10)
        self.assertAlmostEqual(r["rr"], 2.0)


class TestConcentracao(unittest.TestCase):
    def test_gini_extremos(self):
        self.assertAlmostEqual(rs.gini([5, 5, 5, 5]), 0.0)
        self.assertAlmostEqual(rs.gini([0, 0, 0, 10]), 0.75)

    def test_unidades_para_metade(self):
        _, info = rs.concentracao([50, 20, 20, 10])
        self.assertEqual(info["unidades_para_50pct"], 1)
        _, info = rs.concentracao([25, 25, 25, 25])
        self.assertEqual(info["unidades_para_50pct"], 2)


class TestFormatacao(unittest.TestCase):
    def test_numeros_no_padrao_brasileiro(self):
        self.assertEqual(rs.formatar_pct(0.4033), "40,3%")
        self.assertEqual(rs.formatar_pct(-0.09, 0), "−9%")
        self.assertEqual(rs.formatar_num(12123), "12.123")
        self.assertEqual(rs.formatar_num(1.5, 1), "1,5")

    def test_nome_ra(self):
        self.assertEqual(rs.nome_ra("RECANTO DAS EMAS"), "Recanto das Emas")
        self.assertEqual(rs.nome_ra("CEILANDIA"), "Ceilândia")
        self.assertEqual(rs.nome_ra("SCIA/ESTRUTURAL"), "SCIA/Estrutural")
        self.assertEqual(rs.nome_ra("SOBRADINHO II"), "Sobradinho II")
        self.assertEqual(rs.nome_ra("POR DO SOL/SOL NASCENTE"), "Pôr do Sol/Sol Nascente")

    def test_tabela_alinha_numeros_a_direita(self):
        df = pd.DataFrame({"Indicador": ["Física", "Moral"], "Valor": ["40,3%", "14,9%"], "n": [1, 2]})
        separador = rs.tabela_markdown(df).splitlines()[1].strip("|").split("|")
        self.assertTrue(separador[0].startswith(":"))
        self.assertTrue(separador[1].endswith(":"))
        self.assertTrue(separador[2].endswith(":"))


if __name__ == "__main__":
    unittest.main()
