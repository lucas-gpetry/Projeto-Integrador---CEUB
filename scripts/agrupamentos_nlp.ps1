param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$InputPath = "",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($InputPath)) { $InputPath = Join-Path $Root "data\base_analisada.csv" }
if ([string]::IsNullOrWhiteSpace($OutputDir)) { $OutputDir = Join-Path $Root "outputs\agrupamentos_nlp" }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Repair-Mojibake([object]$Value) {
    if ($null -eq $Value) { return $Value }
    $text = [string]$Value
    $hasMojibake = $false
    for ($i = 0; $i -lt ($text.Length - 1); $i++) {
        $current = [int][char]$text[$i]
        $next = [int][char]$text[$i + 1]
        if ($current -in @(0x00C3, 0x00C2, 0x00E2, 0x00F0) -and $next -ge 0x0080 -and $next -le 0x00BF) {
            $hasMojibake = $true
            break
        }
    }
    if (-not $hasMojibake) { return $text }
    try {
        $latin1 = [Text.Encoding]::GetEncoding(28591)
        $repaired = [Text.Encoding]::UTF8.GetString($latin1.GetBytes($text))
        if ($repaired -notmatch "�") { return $repaired }
    } catch { }
    return $text
}

function Is-True([object]$Value) {
    return ([string]$Value).Trim().ToLowerInvariant() -in @("true", "1", "sim", "yes", "y", "t")
}

function Address-Key([object]$Row) {
    $parts = @($Row.cidade, $Row.quadra, $Row.complemento) | ForEach-Object { if ($null -eq $_) { "" } else { ([string]$_).ToUpperInvariant() } }
    return (($parts -join " ") -replace "\s+", " ").Trim()
}

function Safe-Name([string]$Value) {
    $safe = [regex]::Replace($Value, "[^a-zA-Z0-9_]+", "_").Trim("_").ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($safe)) { return "categoria" }
    return $safe
}

$violence = [ordered]@{
    v_fisica = "Violência física"; v_psicologica = "Violência psicológica"; v_patrimonial = "Violência patrimonial"; v_sexual = "Violência sexual"; v_moral = "Violência moral"
}
$context = [ordered]@{
    flag_alcool = "Consumo de álcool"; flag_drogas = "Drogas/entorpecentes"; flag_arma_fogo = "Arma de fogo"; flag_arma_branca = "Arma branca"; flag_tornozeleira = "Tornozeleira/monitoramento"; flag_medida_protetiva = "Medida protetiva"; flag_separacao = "Separação/término"; flag_filhos = "Filhos/crianças"
}
@($violence.Keys) | ForEach-Object { $violence[$_] = Repair-Mojibake $violence[$_] }
@($context.Keys) | ForEach-Object { $context[$_] = Repair-Mojibake $context[$_] }
$allFlags = @($violence.Keys + $context.Keys)
$csvText = [IO.File]::ReadAllText($InputPath, [Text.Encoding]::UTF8)
$rows = @($csvText | ConvertFrom-Csv)
if ($rows.Count -eq 0) { throw "A base de entrada está vazia: $InputPath" }

$prepared = foreach ($row in $rows) {
    foreach ($property in @($row.PSObject.Properties)) {
        if ($property.Value -is [string]) { $property.Value = Repair-Mojibake $property.Value }
    }
    Add-Member -InputObject $row -NotePropertyName endereco_chave -NotePropertyValue (Address-Key $row) -Force
    $row
}
$availableFlags = @($allFlags | Where-Object { $rows[0].PSObject.Properties.Name -contains $_ })
$total = $prepared.Count

$summaryRows = @()
foreach ($flag in $availableFlags) {
    $count = @($prepared | Where-Object { Is-True $_.$flag }).Count
    $group = if ($violence.Contains($flag)) { "violencia" } else { "contexto" }
    $label = if ($violence.Contains($flag)) { $violence[$flag] } else { $context[$flag] }
    $summaryRows += [pscustomobject]@{ grupo = $group; coluna = $flag; categoria = $label; registros = $count; percentual_registros = if ($total) { [math]::Round(100.0 * $count / $total, 2) } else { 0 }; definicao = Repair-Mojibake "flag booleana derivada do histórico por spaCy/Regex" }
}
if ($rows[0].PSObject.Properties.Name -contains "desfecho") {
    foreach ($group in @($prepared | Group-Object { if ([string]::IsNullOrWhiteSpace($_.desfecho)) { "nao_identificado" } else { $_.desfecho } })) {
        $summaryRows += [pscustomobject]@{ grupo = "desfecho"; coluna = "desfecho"; categoria = $group.Name; registros = $group.Count; percentual_registros = if ($total) { [math]::Round(100.0 * $group.Count / $total, 2) } else { 0 }; definicao = Repair-Mojibake "classe categórica derivada do histórico por spaCy" }
    }
}
$summaryRows | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "resumo_nlp.csv")

$caseColumns = @($rows[0].PSObject.Properties.Name) | Select-Object -Unique
foreach ($flag in $availableFlags) {
    @($prepared | Where-Object { Is-True $_.$flag } | Select-Object $caseColumns | Sort-Object endereco_chave, 'data hora') |
        Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir ("casos_{0}.csv" -f (Safe-Name $flag)))
}
if ($rows[0].PSObject.Properties.Name -contains "desfecho") {
    foreach ($group in @($prepared | Group-Object { if ([string]::IsNullOrWhiteSpace($_.desfecho)) { "nao_identificado" } else { $_.desfecho } })) {
        @($group.Group | Select-Object $caseColumns | Sort-Object endereco_chave, 'data hora') |
            Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir ("casos_desfecho_{0}.csv" -f (Safe-Name $group.Name)))
    }
}

$longRows = @()
foreach ($flag in $availableFlags) {
    $label = if ($violence.Contains($flag)) { $violence[$flag] } else { $context[$flag] }
    foreach ($row in @($prepared | Where-Object { Is-True $_.$flag })) {
        $longRows += [pscustomobject]@{ numero = $row.numero; 'data hora' = $row.'data hora'; endereco_chave = $row.endereco_chave; id_celula = $row.id_celula; categoria = $flag; rotulo_categoria = $label }
    }
}
$longRows | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "casos_nlp_formato_longo.csv")

$comboRows = @()
foreach ($row in $prepared) {
    $bits = @($availableFlags | ForEach-Object { if (Is-True $row.$_) { "1" } else { "0" } })
    $active = @($availableFlags | Where-Object { Is-True $row.$_ }) -join ", "
    $comboRows += [pscustomobject]@{ combinacao_flags = $bits -join " + "; flags_ativas = $active }
}
$comboRows = @($comboRows | Group-Object combinacao_flags, flags_ativas | ForEach-Object { [pscustomobject]@{ combinacao_flags = $_.Group[0].combinacao_flags; flags_ativas = $_.Group[0].flags_ativas; registros = $_.Count } } | Sort-Object registros -Descending)
$comboRows | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "combinacoes_flags_nlp.csv")

$addressRows = @()
foreach ($flag in $availableFlags) {
    $label = if ($violence.Contains($flag)) { $violence[$flag] } else { $context[$flag] }
    $flagRows = @($prepared | Where-Object { Is-True $_.$flag })
    foreach ($group in @($flagRows | Group-Object { "{0}|{1}" -f $_.endereco_chave, $_.TIPO_MORADIA })) {
        $parts = $group.Name -split "\|", 2
        $cells = @($group.Group | Where-Object { -not [string]::IsNullOrWhiteSpace($_.id_celula) } | Select-Object -ExpandProperty id_celula -Unique)
        $addressRows += [pscustomobject]@{ categoria = $flag; rotulo_categoria = $label; endereco_chave = $parts[0]; tipo_moradia = $parts[1]; ocorrencias = $group.Count; endereco_repetido = ($group.Count -gt 1); celulas_distintas = $cells.Count; primeira_data = (($group.Group | Sort-Object 'data hora' | Select-Object -First 1).'data hora'); ultima_data = (($group.Group | Sort-Object 'data hora' | Select-Object -Last 1).'data hora') }
    }
}
$addressRows | Sort-Object categoria, @{Expression="ocorrencias"; Descending=$true} | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "agrupamento_endereco_categoria.csv")

$readme = @'
# Agrupamentos NLP

Arquivos gerados a partir de `data/base_analisada.csv` pelo quarto estágio do `main.py` ou diretamente por `scripts/agrupamentos_nlp.py`/`scripts/agrupamentos_nlp.ps1`.

- `resumo_nlp.csv`: quantidade e percentual por categoria.
- `casos_*.csv`: registros classificados em cada flag, com histórico e localização.
- `casos_desfecho_*.csv`: registros separados por classe de desfecho.
- `casos_nlp_formato_longo.csv`: uma linha por registro e categoria ativa.
- `combinacoes_flags_nlp.csv`: coocorrências das flags booleanas.
- `agrupamento_endereco_categoria.csv`: contagem de cada categoria por endereço textual.

As flags são classificações derivadas do texto por Regex e spaCy. `False` não prova que o fator não ocorreu; indica apenas que ele não foi identificado pelas regras atuais. Repetição de uma categoria no mesmo endereço é repetição de registros, não confirmação da mesma vítima ou do mesmo agressor.
'@
Set-Content -LiteralPath (Join-Path $OutputDir "LEIA-ME.md") -Value (Repair-Mojibake $readme) -Encoding UTF8
Write-Output "Agrupamentos NLP gerados em: $OutputDir"
