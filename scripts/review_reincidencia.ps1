param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($OutputDir)) { $OutputDir = Join-Path $Root "outputs\reincidencia_validacao" }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function T([object]$Value) {
    if ($null -eq $Value) { return "" }
    return ([string]$Value).ToUpperInvariant()
}

function CanonicalKey([object]$Row) {
    return (((T $Row.cidade) + " " + (T $Row.quadra) + " " + (T $Row.complemento)) -replace "\s+", " ").Trim()
}

function ParseDate([object]$Value) {
    $date = [datetime]::MinValue
    if ([datetime]::TryParse(([string]$Value), [ref]$date)) { return $date }
    return $null
}

function ParseNumber([object]$Value) {
    $number = 0.0
    $text = ([string]$Value).Replace(',', '.')
    if ([double]::TryParse($text, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$number)) { return $number }
    return $null
}

$rows = @(Import-Csv (Join-Path $Root "data\base_analisada.csv"))
$residential = @($rows | Where-Object { $_.TIPO_MORADIA -in @("CASA", "APARTAMENTO") } | ForEach-Object {
    [pscustomobject]@{
        Key = CanonicalKey $_
        Numero = [string]$_.numero
        Data = ParseDate $_.'data hora'
        DataTexto = [string]$_.'data hora'
        Cidade = [string]$_.cidade
        Quadra = [string]$_.quadra
        Complemento = [string]$_.complemento
        TipoMoradia = [string]$_.TIPO_MORADIA
        Latitude = ParseNumber $_.latitude
        Longitude = ParseNumber $_.longitude
        IdCelula = [string]$_.id_celula
        HistoricoLimpo = [string]$_.historico_limpo
        FlagAlcool = [string]$_.flag_alcool
        FlagMedidaProtetiva = [string]$_.flag_medida_protetiva
    }
})

$coordinateGroups = @($residential | Where-Object { $null -ne $_.Latitude -and $null -ne $_.Longitude } | Group-Object { "{0}|{1}" -f $_.Latitude, $_.Longitude } | Sort-Object Count -Descending)
$dominantCoordinateKey = if ($coordinateGroups.Count -gt 0) { $coordinateGroups[0].Name } else { "" }

$groups = @($residential | Group-Object Key | Where-Object Count -gt 1)
$reviewRows = foreach ($group in $groups) {
    $items = @($group.Group | Sort-Object Data)
    $dates = @($items | Where-Object { $null -ne $_.Data } | ForEach-Object Data)
    $spanDays = if ($dates.Count -gt 1) { [math]::Round(($dates[-1] - $dates[0]).TotalDays, 1) } else { 0 }
    $coordinates = @($items | ForEach-Object { if ($null -ne $_.Latitude -and $null -ne $_.Longitude) { "{0:F5},{1:F5}" -f $_.Latitude, $_.Longitude } } | Sort-Object -Unique)
    $cells = @($items | ForEach-Object IdCelula | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
    $sameTimestamp = @($items | Group-Object DataTexto | Where-Object Count -gt 1).Count
    $incompleteRows = @($items | Where-Object {
        [string]::IsNullOrWhiteSpace(([string]$_.Quadra).Trim()) -or
        [string]::IsNullOrWhiteSpace(([string]$_.Complemento).Trim())
    }).Count
    $genericRows = @($items | Where-Object {
        [string]::IsNullOrWhiteSpace(([string]$_.Quadra).Trim()) -or
        ([string]$_.Complemento -match "^(CASA|APTO|APARTAMENTO)\s*\d*\s*$")
    }).Count
    $sameCoord = @($items | Group-Object { "{0:F5},{1:F5}" -f $_.Latitude, $_.Longitude } | Where-Object Count -gt 1).Count
    $dominantRows = @($items | Where-Object { ("{0}|{1}" -f $_.Latitude, $_.Longitude) -eq $dominantCoordinateKey }).Count
    $historySnippets = @($items | ForEach-Object {
        $clean = (($_.HistoricoLimpo -replace "\s+", " ").Trim())
        $clean.Substring(0, [math]::Min(240, $clean.Length))
    })

    $quality = if ($sameTimestamp -gt 0) { "DUPLICIDADE_OU_MESMO_EVENTO" }
        elseif ($dominantRows -eq $items.Count -and $dominantRows -gt 0) { "COORDENADA_DOMINANTE_SEM_LOCALIZACAO" }
        elseif ($genericRows -gt 0) { "CHAVE_FRACA" }
        elseif ($coordinates.Count -gt 1 -or $cells.Count -gt 1) { "LOCALIZACAO_INCONSISTENTE" }
        else { "REINCIDENCIA_PLAUSIVEL" }

    [pscustomobject]@{
        FrequenciaChamados = [int]$group.Count
        ReincidenciasAposPrimeiro = [int]$group.Count - 1
        QualidadeInicial = $quality
        Cidade = $items[0].Cidade
        Quadra = $items[0].Quadra
        Complemento = $items[0].Complemento
        ChaveNormalizada = $group.Name
        IntervaloDias = $spanDays
        CoordenadasDistintas = $coordinates.Count
        CelulasDistintas = $cells.Count
        LinhasCoordenadaDominante = $dominantRows
        GruposMesmoTimestamp = $sameTimestamp
        LinhasComEnderecoIncompleto = $incompleteRows
        LinhasComEnderecoFraco = $genericRows
        Numeros = (($items | ForEach-Object Numero) -join " | ")
        Datas = (($items | ForEach-Object DataTexto) -join " | ")
        Historicos = ($historySnippets -join " || ")
    }
}

$reviewRows | Sort-Object FrequenciaChamados, QualidadeInicial, Cidade, Quadra, Complemento | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "revisao_semantica_grupos.csv")

$summary = $reviewRows | Group-Object QualidadeInicial | Sort-Object Name | ForEach-Object {
    [pscustomobject]@{
        Classificacao = $_.Name
        Enderecos = $_.Count
        Registros = [int](($_.Group | Measure-Object FrequenciaChamados -Sum).Sum)
    }
}
$summary | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "revisao_semantica_resumo.csv")
$summary | Format-Table -AutoSize
Write-Output "Revisão semântica gravada em: $OutputDir"
