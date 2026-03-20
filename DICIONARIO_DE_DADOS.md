# Dicionário de Dados: `base_analisada.csv`

Este documento descreve as variáveis presentes na base final gerada pelo pipeline do Projeto PMDF. Esta base combina dados brutos da polícia com engenharia de atributos temporais, geoespaciais e de processamento de linguagem natural (NLP).

## 1. Identificação e Localização Bruta
Dados extraídos diretamente do sistema original, sem interferência preditiva.

| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `numero` | String | Código identificador único da ocorrência policial (B.O.). |
| `incidencia` | String | Tipo de crime ou infração registrada originalmente (ex: LEI 11.340 MARIA DA PENHA). |
| `cidade` | String | Região Administrativa (RA) onde ocorreu o fato (ex: SAMAMBAIA, CEILÂNDIA). |
| `bairro` / `quadra` / `complemento` | String | Detalhamento bruto do endereço digitado pelo policial. |
| `latitude` / `longitude` | Float | Coordenadas GPS da viatura no momento do registro. |

## 2. Dados Textuais
| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `historico` | String | Relato completo original escrito pelo policial militar. |
| `historico_limpo` | String | Histórico padronizado (sem acentos, em minúsculas e sem caracteres especiais) preparado para o algoritmo de Inteligência Artificial. |

## 3. Features Temporais (Extraídas)
Variáveis essenciais para captura de sazonalidade e padrões de rotina pelo algoritmo.

| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `data hora` | Datetime | Data e hora exatas do registro consolidadas. |
| `ano`, `mes`, `dia` | Inteiro | Componentes de data separados para análise de série temporal. |
| `hora`, `minuto`, `segundo`| Inteiro | Componentes de horário separados. |
| `TURNO` | Categórico | Período do dia agrupado em 4 faixas: `Madrugada` (0h-5h), `Manhã` (6h-11h), `Tarde` (12h-17h) e `Noite` (18h-23h). |

## 4. Features Geoespaciais (Clusterização)
Variáveis criadas pela Frente de Análise Espacial para padronizar o "Onde" ocorreu o crime.

| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `TIPO_MORADIA` | Categórico | Classificação do ambiente físico da ocorrência extraída via Regex. Valores: `CASA`, `APARTAMENTO`, `VIA PUBLICA`, `COMERCIO / SERVICO` ou `OUTROS / NÃO IDENTIFICADO`. |
| `id_celula` | Inteiro | **(Variável Chave Preditiva)** ID numérico do quadrante de 500x500 metros onde o crime ocorreu. *Nota: Cerca de 5.600 linhas possuem este campo nulo (NaN) propositalmente devido a ruídos no GPS original. O modelo preditivo espacial deve treinar apenas com linhas não-nulas.* |

## 5. Features Comportamentais e Contextuais (I.A. / NLP)
*Flags* geradas pelo processamento de Linguagem Natural (spaCy) lendo o `historico_limpo`. Identificam a dinâmica da violência e agravantes de risco.

### 5.1 Tipos de Violência Mapeados
| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `v_fisica` | Booleano | `True` se houve contato físico violento (socos, chutes, tapas, empurrões, espancamento). |
| `v_psicologica` | Booleano | `True` se houve ameaça verbal, humilhação, xingamento grave ou perseguição. |
| `v_patrimonial` | Booleano | `True` se o agressor quebrou, rasgou, subtraiu ou destruiu bens da vítima (celular, móveis, carro). |
| `v_sexual` | Booleano | `True` se houve menção a violência sexual, estupro ou atos libidinosos forçados. |
| `v_moral` | Booleano | `True` se houve calúnia, difamação ou injúria contra a honra da vítima. |

### 5.2 Agravantes e Fatores de Risco
| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `flag_alcool` / `flag_drogas` | Booleano | `True` se o B.O. cita embriaguez, consumo de álcool ou uso de entorpecentes pelo agressor. |
| `flag_arma_fogo` | Booleano | `True` se houve uso ou ameaça com arma de fogo (revólver, pistola, disparo). |
| `flag_arma_branca` | Booleano | `True` se houve uso de faca, canivete, facão ou tesoura. |
| `flag_medida_protetiva`| Booleano | `True` se o B.O. menciona quebra/descumprimento de Medida Protetiva vigente. |
| `flag_tornozeleira` | Booleano | `True` se o agressor estava sob monitoramento eletrônico. |
| `flag_separacao` | Booleano | `True` se o conflito foi motivado por término recente, separação ou envolve "ex-companheiro". |
| `flag_filhos` | Booleano | `True` se havia filhos da vítima/casal presentes ou envolvidos no contexto da ocorrência. |

### 5.3 Desfecho da Ocorrência
| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `desfecho` | Categórico | Ação tomada pela PMDF. Valores: `encaminhado_dp` (conduzido à delegacia), `resolvido_local` (acordo/orientação no local) ou `nao_identificado`. |