"""Testes das conversões da EDA SINAN.

Executar a partir da raiz do projeto: python -m unittest discover -s tests
"""

import unittest

import numpy as np
import pandas as pd

from src import sinan_eda as eda


class TestDecodificacao(unittest.TestCase):
    def test_idade_codificada_e_em_anos(self):
        idade = eda.decodificar_idade(pd.Series(["4025", "3006", "2010", "1005", "37", "", "4999", "500"]))
        np.testing.assert_array_equal(idade.values, [25, 0, 0, 0, 37, np.nan, np.nan, np.nan])

    def test_hora_em_formatos_diversos(self):
        hora = eda.hora_ocorrencia(pd.Series(["14:30", "9:05", "1430", "930", "07", "22h15", "", "25:00", "14:30:00"]))
        np.testing.assert_array_equal(hora.values, [14, 9, 14, 9, 7, 22, np.nan, np.nan, 14])

    def test_normalizar_codigos(self):
        s = eda.normalizar_codigos(pd.Series(["01", "1.0", " 9 ", "00", "", None, "F"]))
        self.assertEqual(s.tolist(), ["1", "1", "9", "0", "", "", "F"])


class TestTabelas(unittest.TestCase):
    def test_flags_usam_respostas_validas(self):
        df = pd.DataFrame({"VIOL_FISIC": ["1", "1", "2", "9", ""]})
        t = eda.tabela_flags(df, {"VIOL_FISIC": "Física"}).iloc[0]
        self.assertEqual((t["sim"], t["nao"], t["nao_informado"]), (2, 1, 2))
        self.assertAlmostEqual(t["p"], 2 / 3)
        self.assertAlmostEqual(t["p_sobre_total"], 2 / 5)

    def test_distribuicao_separa_ignorado_e_nao_se_aplica(self):
        t = eda.distribuicao(pd.Series(["1", "1", "2", "9", "8", "7"]), {"1": "A", "2": "B"}).set_index("categoria")
        self.assertEqual(t.loc["Ignorado/vazio", "n"], 1)
        self.assertEqual(t.loc["Não se aplica", "n"], 1)
        self.assertEqual(t.loc["Código não previsto", "n"], 1)
        self.assertAlmostEqual(t.loc["A", "pct_validas"], 2 / 3)
        self.assertTrue(np.isnan(t.loc["Ignorado/vazio", "pct_validas"]))

    def test_vinculo_segue_hierarquia(self):
        df = pd.DataFrame({"REL_CONJ": ["1", "2", "2"], "REL_PAI": ["1", "1", "2"], "REL_DESCO": ["2", "2", "2"]})
        self.assertEqual(eda.grupo_vinculo(df).tolist(), ["Parceiro ou ex-parceiro íntimo", "Familiar", "Não informado"])


if __name__ == "__main__":
    unittest.main()
