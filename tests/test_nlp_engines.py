"""Casos de regressão das regras de PLN.

Executar a partir da raiz do projeto: python -m unittest discover -s tests
"""

import unittest

import spacy

from src.clean_data import limpar_historico
from src.utils.nlp_engines import (
    extrair_flags_adicionais,
    extrair_flags_regex,
    extrair_tipos_spacy,
    normalizar_para_nlp,
    termo_negado,
)

NLP = spacy.load("pt_core_news_sm", disable=["ner", "textcat"])


def classificar(texto):
    """Reproduz o fluxo do analysis.py para um único histórico."""
    doc = NLP(normalizar_para_nlp(texto))
    return {
        **extrair_flags_regex(limpar_historico(texto)),
        **extrair_tipos_spacy(doc),
        **extrair_flags_adicionais(doc),
    }


class TestEscopoNegacao(unittest.TestCase):
    def test_gatilho_com_palavras_transparentes(self):
        self.assertTrue(termo_negado("o autor nao a teria agredido".split(), 5))

    def test_palavra_nao_transparente_encerra_escopo(self):
        self.assertFalse(termo_negado("nao respeitou a medida".split(), 3))

    def test_negacao_de_violencia_fisica(self):
        self.assertFalse(classificar("O autor não agrediu a vítima.")["v_fisica"])
        self.assertFalse(classificar("Ela disse que o autor não a agrediu.")["v_fisica"])

    def test_pseudo_negacoes_mantem_o_termo(self):
        self.assertTrue(classificar("O autor não só agrediu a vítima como a xingou.")["v_fisica"])
        self.assertTrue(classificar("O autor não parava de agredir a vítima.")["v_fisica"])

    def test_sem_lesoes(self):
        self.assertFalse(classificar("A vítima estava sem lesões aparentes.")["v_fisica"])
        self.assertFalse(classificar("A vítima não apresentava sinais de lesões.")["v_fisica"])
        self.assertFalse(classificar("A senhora não apresenta lesões aparentes.")["v_fisica"])
        self.assertFalse(classificar("Ambos não apresentavam lesões aparentes.")["v_fisica"])
        self.assertFalse(classificar("O indivíduo não apresentava quaisquer lesões.")["v_fisica"])

    def test_negacao_nas_flags_regex(self):
        self.assertFalse(classificar("A vítima não possui medida protetiva.")["flag_medida_protetiva"])
        self.assertTrue(classificar("O autor não respeitou a medida protetiva.")["flag_medida_protetiva"])
        self.assertFalse(classificar("O autor não estava embriagado.")["flag_alcool"])
        self.assertFalse(classificar("O autor estava sem arma de fogo.")["flag_arma_fogo"])


class TestDicionarios(unittest.TestCase):
    def test_ameaca_verbo_e_substantivo(self):
        self.assertTrue(classificar("O autor ameaçou a vítima de morte.")["v_psicologica"])
        self.assertTrue(classificar("O autor fez ameaças contra a vítima.")["v_psicologica"])

    def test_formas_da_definicao_de_violencia_fisica(self):
        self.assertTrue(classificar("Ela relatou empurrões.")["v_fisica"])
        self.assertTrue(classificar("A vítima apresentava lesões no braço.")["v_fisica"])

    def test_plurais_e_derivacoes_nas_regex(self):
        self.assertTrue(classificar("O autor é usuário de drogas.")["flag_drogas"])
        self.assertTrue(classificar("O autor estava alcoolizado.")["flag_alcool"])
        self.assertTrue(classificar("O autor efetuou disparos.")["flag_arma_fogo"])
        self.assertTrue(classificar("Foram apreendidas duas facas.")["flag_arma_branca"])
        self.assertTrue(classificar("A vítima possui medidas protetivas.")["flag_medida_protetiva"])
        self.assertTrue(classificar("Houve descumprimento das MPUs.")["flag_medida_protetiva"])

    def test_improcedencia_zera_violencias(self):
        resultado = classificar("Nada constatado. O autor teria agredido a vítima.")
        self.assertFalse(any(resultado[c] for c in ["v_fisica", "v_psicologica", "v_patrimonial", "v_sexual", "v_moral"]))


class TestSeparacao(unittest.TestCase):
    def test_ex_parceiro(self):
        self.assertTrue(classificar("O ex-marido da vítima chegou à residência.")["flag_separacao"])
        self.assertTrue(classificar("O ex companheiro voltou a procurá-la.")["flag_separacao"])

    def test_fim_como_conectivo(self):
        self.assertFalse(classificar("Por fim, a vítima foi orientada.")["flag_separacao"])
        self.assertFalse(classificar("O autor saiu a fim de comprar cigarros.")["flag_separacao"])

    def test_fim_do_relacionamento_nao_aceito(self):
        self.assertTrue(classificar("O autor não aceita o fim do relacionamento.")["flag_separacao"])

    def test_termino_de_outra_coisa(self):
        self.assertFalse(classificar("A equipe aguardou o término do registro.")["flag_separacao"])
        self.assertFalse(classificar("Os agentes deslocaram para terminar a ocorrência.")["flag_separacao"])
        self.assertFalse(classificar("Houve o rompimento da tornozeleira.")["flag_separacao"])
        self.assertTrue(classificar("Ela relatou que terminou seu relacionamento há um mês.")["flag_separacao"])

    def test_separar_briga(self):
        self.assertFalse(classificar("A guarnição separou os dois.")["flag_separacao"])
        self.assertTrue(classificar("O casal está separado há dois meses.")["flag_separacao"])
        self.assertTrue(classificar("Eles já estavam separados há vários dias.")["flag_separacao"])
        self.assertFalse(classificar("A senhora foi ouvida em separado.")["flag_separacao"])
        self.assertFalse(classificar("Eles dormiam em quartos separados.")["flag_separacao"])


class TestDesfecho(unittest.TestCase):
    def test_local_nao_define_desfecho(self):
        self.assertEqual(classificar("Chegando ao local, a vítima apresentava lesões.")["desfecho"], "nao_identificado")

    def test_orientacao_no_local(self):
        self.assertEqual(classificar("Chegando ao local, a vítima foi orientada.")["desfecho"], "resolvido_local")

    def test_apresentacao_na_deam(self):
        self.assertEqual(classificar("O autor foi apresentado na DEAM.")["desfecho"], "encaminhado_dp")

    def test_conducao_tem_prioridade(self):
        resultado = classificar("A vítima foi orientada e o autor foi conduzido à delegacia.")
        self.assertEqual(resultado["desfecho"], "encaminhado_dp")


if __name__ == "__main__":
    unittest.main()
