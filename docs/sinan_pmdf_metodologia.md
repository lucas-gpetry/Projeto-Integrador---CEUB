# Metodologia de integração SINAN × PMDF

## Decisão arquitetural

O SINAN e a PMDF permanecem como fontes independentes. A integração ocorre somente no nível
agregado de mês de ocorrência e de indicadores de violência. Não são usados identificadores
de pessoa, endereço, protocolo ou texto livre para relacionar registros.

## Coortes SINAN

O recorte territorial é `ID_MN_OCOR = 530010` (ocorrência em Brasília/DF), e não o município
de residência. A coorte primária exige sexo feminino, data analítica entre 2010 e 2025 e
`LES_AUTOP = 2` (violência não autoprovocada confirmada). A análise de sensibilidade inclui
códigos de autoprovocada ignorados ou vazios, mas continua excluindo `LES_AUTOP = 1`.

Quando `DT_OCOR` é inválida ou ausente, `DT_NOTIFIC` é usada apenas como *fallback* e o campo
`fonte_data_analitica` mantém essa rastreabilidade. A base bruta não é modificada.

## Indicadores comparáveis

São comparados volume, violência física, psicológica e sexual, arma de fogo, objeto
perfurocortante e suspeita de álcool pelo autor. Cada comparação traz contagens e proporções
mensais, além de Pearson e Spearman em 12 observações (janeiro a dezembro de 2024).

Essas correlações são exploratórias: não demonstram causalidade, concordância entre fontes,
cobertura do atendimento ou subnotificação.

O *deep dive* também avalia sazonalidade, coocorrências internas e defasagens de −3 a +3
meses. Como a varredura de defasagens multiplica os testes, os p-valores de Pearson recebem
ajuste de Benjamini-Hochberg; somente resultados com valor ajustado abaixo de 0,05 podem ser
considerados sinal estatístico exploratório.

## Reincidência

`OUT_VEZES` do SINAN é o histórico de violência relatado na notificação. A reincidência PMDF
é uma repetição de endereço no conjunto de chamados. Como a unidade e o significado são
distintos, essas medidas não são unidas nem correlacionadas.

## Referências

- Ministério da Saúde. [VIVA/SINAN — Vigilância de Violências e Acidentes](https://www.gov.br/saude/pt-br/composicao/svsa/inqueritos-de-saude/viva-sinan).
- Ministério da Saúde. [Instrutivo de notificação de violência interpessoal e autoprovocada](https://bvsms.saude.gov.br/bvs/publicacoes/viva_instrutivo_violencia_interpessoal_autoprovocada_2ed.pdf).
