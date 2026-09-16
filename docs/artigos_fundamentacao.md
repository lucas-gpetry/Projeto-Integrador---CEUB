# Artigos de fundamentação do projeto

Este documento apresenta dois artigos localizados no Google Acadêmico, ambos com acesso ao texto completo sem pagamento, e explica como suas abordagens teóricas e metodológicas se relacionam com o projeto de análise das ocorrências da Lei Maria da Penha registradas pela PMDF.

## 1. Domestic abuse hot spots: A longitudinal, place-based analysis of 13 years of initial reports to the police

**Referência:** Kumar, S. et al. (2024). *Domestic abuse hot spots: A longitudinal, place-based analysis of 13 years of initial reports to the police*. *Policing: A Journal of Policy and Practice*, 18, paae056. DOI: [10.1093/police/paae056](https://doi.org/10.1093/police/paae056).

- [Buscar no Google Acadêmico](https://scholar.google.com/scholar?q=%22Domestic+abuse+hot+spots%22+Kumar+Ariel)
- [Texto completo gratuito](https://academic.oup.com/policing/article/18/1/paae056/7739691)

### Teoria e conceitos centrais

O artigo parte da criminologia ambiental e da teoria da concentração criminal. Essas abordagens defendem que os crimes não se distribuem uniformemente pelo território: uma pequena parcela dos locais tende a concentrar uma parcela desproporcional das ocorrências.

Os autores articulam quatro conceitos principais:

- **Hotspots:** locais com concentração elevada de ocorrências.
- **Micro-lugares:** endereços ou pequenos trechos de rua, em vez de bairros inteiros.
- **Revitimização ou repetição:** ocorrência de novos chamados no mesmo local ao longo do tempo.
- **Trajetórias temporais:** evolução dos locais de baixa ou alta ocorrência durante vários períodos.

O trabalho também discute explicações possíveis para a concentração espacial, como características sociodemográficas compartilhadas, desorganização social e menor eficácia coletiva. Essas hipóteses não significam que o local cause diretamente a violência; elas indicam que determinados contextos podem favorecer sua persistência ou aumentar a probabilidade de acionamento policial.

### Método e resultados

Os pesquisadores realizaram uma análise longitudinal retrospectiva de 1,7 milhão de chamadas iniciais à polícia em Londres, entre 2007 e 2019. Foram utilizadas estatísticas espaciais e modelagem de trajetórias para estudar a concentração dos registros, a repetição em endereços específicos e a evolução dos hotspots.

O estudo diferenciou a simples quantidade de ocorrências de uma medida de **dano criminal**, que considera a gravidade dos eventos. Os principais resultados foram:

- uma pequena parcela dos endereços concentrou uma quantidade desproporcional de registros;
- entre 57,9% e 85,8% dos locais analisados apresentaram repetição de violência doméstica em algum período;
- a repetição anual em endereços específicos foi estimada em 69,9%;
- a probabilidade média de um novo registro no mesmo endereço no mês seguinte foi de 41%;
- mudanças em menos de 1% dos locais explicaram grande parte da variação observada na violência em Londres.

Os autores concluem que os chamados iniciais à polícia podem revelar uma repetição maior do que aquela observada em registros criminais já filtrados pelo sistema de justiça. Dessa forma, a análise por micro-lugares pode auxiliar na priorização de medidas preventivas. [Resumo e resultados do artigo](https://cris.huji.ac.il/en/publications/domestic-abuse-hot-spots-a-longitudinal-place-based-analysis-of-1/) · [Discussão metodológica](https://academic.oup.com/policing/article/18/1/paae056/7739691)

### Relação com o projeto

O artigo fundamenta diretamente quatro componentes implementados no projeto:

1. **Repetição por endereço** — o projeto agrupa ocorrências a partir de cidade, quadra e complemento. Essa unidade é semelhante ao uso de endereços como micro-lugares no artigo.
2. **Grade espacial de 500 metros** — a grade permite identificar áreas com maior concentração de chamados e comparar o risco entre células.
3. **Mapas de hotspots** — a visualização dos chamados, dos batalhões e dos feminicídios segue a lógica de localizar concentrações e orientar a prevenção.
4. **Priorização operacional** — os resultados apoiam a ideia de direcionar recursos para poucos locais com alta frequência ou gravidade, em vez de distribuir a resposta de maneira uniforme.

### Limitações e cuidados para o projeto

O conceito de repetição por endereço não deve ser interpretado automaticamente como reincidência da mesma vítima ou do mesmo agressor. Um endereço pode representar uma residência individual, um prédio com várias famílias ou diferentes pessoas atendidas no mesmo local. Portanto, a formulação mais rigorosa para o relatório é:

> “repetição de ocorrências no mesmo endereço” ou “reincidência espacial de chamados”.

Também é necessário considerar a diferença de escala e período. O artigo usa 13 anos de dados e endereços como unidade principal, enquanto o projeto analisa sobretudo o ano de 2025 e utiliza uma grade de 500 metros para a parte geoespacial. Assim, o projeto identifica concentração anual, mas ainda não demonstra que os hotspots permanecem estáveis ao longo de vários anos.

## 2. Harnessing Machine Learning in Tackling Domestic Violence—An Integrative Review

**Referência:** Hui, V.; Constantino, R. E.; Lee, Y. J. (2023). *Harnessing Machine Learning in Tackling Domestic Violence—An Integrative Review*. *International Journal of Environmental Research and Public Health*, 20(6), 4984. DOI: [10.3390/ijerph20064984](https://doi.org/10.3390/ijerph20064984).

- [Buscar no Google Acadêmico](https://scholar.google.com/scholar?q=%22Harnessing+Machine+Learning+in+Tackling+Domestic+Violence%22)
- [Texto completo gratuito no PubMed Central](https://pmc.ncbi.nlm.nih.gov/articles/PMC10049304/)
- [Versão no periódico](https://www.mdpi.com/1660-4601/20/6/4984)

### Teoria e conceitos centrais

O artigo não propõe uma teoria social única sobre a origem da violência doméstica. Sua contribuição é metodológica: registros policiais, clínicos, jornalísticos e de redes sociais contêm sinais de risco, padrões de comportamento e indícios de revitimização que podem ser extraídos por técnicas de aprendizado de máquina.

Os autores organizam as aplicações de machine learning em três finalidades:

- **Classificação:** identificar se um registro pertence a uma categoria, como presença de violência ou alto risco.
- **Predição:** estimar a probabilidade de um evento futuro, como nova ocorrência ou revitimização.
- **Exploração:** descobrir temas, agrupamentos e padrões que não foram definidos antecipadamente.

O artigo também diferencia:

- **Aprendizado supervisionado:** utiliza registros rotulados para aprender a classificar ou prever um resultado.
- **Aprendizado não supervisionado:** procura estruturas e grupos em dados sem rótulos prévios.
- **Processamento de linguagem natural:** transforma textos em variáveis, temas, entidades e indicadores analisáveis.

Essa perspectiva é importante porque a violência doméstica é registrada em fontes heterogêneas e frequentemente incompletas. O modelo computacional pode encontrar padrões, mas a qualidade da conclusão depende da qualidade, padronização e representatividade dos dados de origem.

### Método e resultados

Os autores fizeram uma revisão integrativa de 3.588 estudos encontrados em bases como PubMed, Scopus e Google Acadêmico. Após a remoção de duplicidades e a triagem dos textos, 22 estudos foram incluídos.

Entre os estudos analisados:

- 12 utilizaram aprendizado supervisionado;
- 7 utilizaram aprendizado não supervisionado;
- 3 combinaram as duas abordagens;
- 12 utilizaram dados de redes sociais;
- 5 utilizaram anotações profissionais;
- 3 utilizaram bases nacionais;
- os algoritmos mais frequentes foram Random Forest, Support Vector Machine e Naive Bayes;
- as finalidades incluíram classificação de risco, previsão de violência futura, revitimização e descoberta de temas em textos.

Os autores concluem que o machine learning tem potencial para classificação, previsão e exploração de dados de violência doméstica. Entretanto, destacam como principais obstáculos a dificuldade de adoção, a heterogeneidade das fontes, a preparação demorada dos dados, a falta de padronização e os desafios de interpretação e uso ético. [Texto integral e resultados](https://pmc.ncbi.nlm.nih.gov/articles/PMC10049304/) · [Versão do periódico](https://www.mdpi.com/1660-4601/20/6/4984)

### Relação com o projeto

O artigo se relaciona principalmente às partes de processamento de linguagem natural e ao roadmap de machine learning do projeto.

#### Processamento dos relatos policiais

No projeto, os históricos das ocorrências são processados para identificar termos relacionados a álcool, drogas, violência física, violência psicológica, medida protetiva e término de relacionamento. Essa etapa transforma texto não estruturado em variáveis analíticas.

Quando o projeto cria a variável `flag_alcool` a partir de termos como “embriaguez”, “bebida” e “cerveja”, está realizando uma classificação baseada em regras. Essa estratégia é útil como prova de conceito e para criar variáveis iniciais, mas é diferente de um modelo de machine learning treinado com exemplos rotulados.

#### Diferença entre regras, NLP e machine learning

- **Regex e dicionários:** procuram padrões previamente definidos.
- **NLP:** limpa, estrutura e representa o texto para análise.
- **Machine learning:** aprende padrões a partir de exemplos e tenta generalizar para novos registros.

Assim, a implementação atual do projeto representa uma etapa de preparação e exploração. Ela ainda não constitui um modelo preditivo de reincidência ou feminicídio.

#### Base para o roadmap

O artigo apoia a evolução futura do projeto para modelos capazes de:

- classificar ocorrências com maior risco;
- estimar a probabilidade de um novo chamado;
- identificar padrões textuais associados à escalada da violência;
- descobrir grupos de ocorrências com características semelhantes;
- combinar variáveis textuais, temporais e geográficas.

Uma possibilidade seria definir como variável-alvo a existência de uma nova ocorrência no mesmo endereço nos 30, 60 ou 90 dias seguintes. As variáveis explicativas poderiam incluir histórico de chamados, intervalo entre ocorrências, álcool, descumprimento de medida protetiva, tipo de violência, horário, dia da semana, célula de 500 metros e distância até o batalhão mais próximo.

### Limitações e cuidados para o projeto

Os modelos analisados pelo artigo podem reproduzir limitações existentes nos registros. No projeto:

- a base representa violência notificada, não toda a violência ocorrida;
- a ausência de uma palavra no boletim não prova a ausência do fator;
- maior número de registros pode refletir maior propensão a denunciar ou maior presença policial;
- regras baseadas em palavras podem gerar falsos positivos e falsos negativos;
- um modelo que prevê novos chamados pode aprender padrões de registro policial, e não a ocorrência real da violência.

Por isso, os resultados devem ser apresentados como **associações e sinais de risco**, não como provas de causalidade. A presença de álcool, por exemplo, pode estar associada a determinados horários e tipos de ocorrência, mas a análise descritiva não demonstra que o álcool causou a agressão.

## Complementaridade dos artigos

Os dois trabalhos sustentam dimensões diferentes do projeto:

| Dimensão | Kumar et al. (2024) | Hui et al. (2023) |
|---|---|---|
| Foco principal | Espaço, tempo e repetição | Dados, NLP e machine learning |
| Unidade de análise | Endereço e micro-lugar | Registro, texto e conjunto de dados |
| Aplicação no projeto | Hotspots, grade de 500 m e repetição por endereço | Flags textuais, preparação dos dados e roadmap de ML |
| Principal contribuição | Mostra que poucos locais concentram muitos chamados | Mostra como transformar dados complexos em sinais analíticos |
| Principal cautela | Endereço não identifica necessariamente a mesma vítima | Registro policial não representa toda a violência |

Em conjunto, os artigos permitem formular a fundamentação do projeto da seguinte forma:

> A violência doméstica apresenta concentração espacial e repetição em determinados locais, o que permite identificar hotspots e priorizar ações preventivas. Paralelamente, os registros policiais contêm informações textuais e contextuais que podem ser estruturadas por NLP e, futuramente, utilizadas em modelos de classificação e previsão. Entretanto, a análise deve distinguir repetição de ocorrências no endereço de reincidência individual e reconhecer que os dados policiais representam apenas a violência notificada.

## Referências

- [[src/relatorio_final.qmd]] — relatório analítico que contém as análises de NLP, reincidência por endereço e geoespacial.
- [Kumar et al. (2024) — artigo completo](https://academic.oup.com/policing/article/18/1/paae056/7739691).
- [Hui, Constantino e Lee (2023) — artigo completo](https://pmc.ncbi.nlm.nih.gov/articles/PMC10049304/).
