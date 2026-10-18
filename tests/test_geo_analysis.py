"""Casos de regressão da classificação do tipo de local e da supressão nos mapas publicados.

Executar a partir da raiz do projeto: python -m unittest discover -s tests
"""

import unittest

import pandas as pd

from src.geo_analysis import (
    K_MINIMO_CELULA,
    celulas_publicaveis,
    classificar_tipo_local,
    feminicidios_por_ra,
    rotulo_contagem,
)


def classificar(quadra, complemento=""):
    return classificar_tipo_local(pd.Series([quadra]), pd.Series([complemento])).iloc[0]


class TestTipoLocal(unittest.TestCase):
    def test_categorias_basicas(self):
        self.assertEqual(classificar("QR 403", "CASA 12"), "CASA")
        self.assertEqual(classificar("SQS 308", "BLOCO C APTO 204"), "APARTAMENTO")
        self.assertEqual(classificar("BR-020", "KM 12"), "VIA PUBLICA")
        self.assertEqual(classificar("RODOVIA DF-001", ""), "VIA PUBLICA")
        self.assertEqual(classificar("SETOR COMERCIAL", "BAR DO ZE"), "COMERCIO / SERVICO")

    def test_precedencia(self):
        self.assertEqual(classificar("QD 10", "CASA 5 APTO 2"), "APARTAMENTO")
        self.assertEqual(classificar("RUA 3", "CASA 15"), "CASA")

    def test_sem_casamento_parcial(self):
        # "BR" e "BAR" dentro de outras palavras não classificam o local.
        self.assertEqual(classificar("SOBRADO", "FUNDOS"), "OUTROS / NÃO IDENTIFICADO")
        self.assertEqual(classificar("BARRACO", ""), "OUTROS / NÃO IDENTIFICADO")

    def test_conjunto_nao_e_casa(self):
        self.assertEqual(classificar("QNM 10", "CONJUNTO A"), "OUTROS / NÃO IDENTIFICADO")

    def test_nulos(self):
        resultado = classificar_tipo_local(pd.Series([None]), pd.Series([None])).iloc[0]
        self.assertEqual(resultado, "OUTROS / NÃO IDENTIFICADO")


class TestSupressaoMapas(unittest.TestCase):
    def test_celulas_abaixo_do_limite_saem_do_mapa(self):
        contagem = pd.DataFrame({"id_celula": [1, 2, 3], "total_ocorrencias": [K_MINIMO_CELULA - 1, K_MINIMO_CELULA, 40]})
        self.assertEqual(celulas_publicaveis(contagem)["id_celula"].tolist(), [2, 3])

    def test_feminicidios_contados_por_ra(self):
        contagem = feminicidios_por_ra(pd.Series([" Ceilândia", "CEILÂNDIA", "GAMA", None]))
        self.assertEqual(contagem.to_dict(), {"CEILÂNDIA": 2, "GAMA": 1})

    def test_contagem_pequena_nao_e_exibida(self):
        self.assertEqual(rotulo_contagem(2), "menos de 3 casos")
        self.assertEqual(rotulo_contagem(3), "3 casos")


if __name__ == "__main__":
    unittest.main()
