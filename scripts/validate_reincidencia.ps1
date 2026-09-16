param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $Root "outputs\reincidencia_validacao"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Get-Text([object]$Value) {
    if ($null -eq $Value) { return "" }
    return ([string]$Value).ToUpperInvariant()
}

function Normalize-Label([object]$Value) {
    if ($null -eq $Value) { return "" }
    $text = ([string]$Value).ToUpperInvariant().Normalize([Text.NormalizationForm]::FormD)
    return ([regex]::Replace($text, "\p{Mn}", ""))
}

function Get-AddressKey([object]$Row) {
    return ((Get-Text $Row.cidade) + " " + (Get-Text $Row.quadra) + " " + (Get-Text $Row.complemento))
}

function Get-CanonicalAddressKey([object]$Row) {
    $key = Get-AddressKey $Row
    return (($key -replace "\s+", " ").Trim())
}

function Get-ResidentialType([string]$Key) {
    $isApt = $Key -match "APTO|APARTAMENTO|APT|BLOCO|EDIF|ED\.|ANDAR|KITNET|RESIDENCIAL"
    $isCasa = $Key -match "CASA|LOTE|CHACARA|FAZENDA|CONJUNTO"

    if ($isCasa) { $type = "CASA" } else { $type = "OUTROS / NAO IDENTIFICADO" }
    if ($isApt) { $type = "APARTAMENTO" }
    if ($Key -match "RUA|AVENIDA|ESTACIONAMENTO|PARQUE|PRACA|VIA|BR|DF-|PASSARELA" -and $type -eq "OUTROS / NAO IDENTIFICADO") { $type = "VIA PUBLICA" }
    if ($Key -match "BAR|LOJA|MERCADO|FARMACIA|SHOPPING|POSTO|DISTRIBUIDORA|RESTAURANTE|COMERCIO" -and $type -eq "OUTROS / NAO IDENTIFICADO") { $type = "COMERCIO / SERVICO" }
    return $type
}

function Get-Number([object]$Value) {
    $parsed = 0.0
    $ok = [double]::TryParse(([string]$Value), [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$parsed)
    if ($ok) { return $parsed }
    return $null
}

function Test-PointInPolygon([double]$X, [double]$Y, [object[]]$Polygon) {
    $inside = $false
    $j = $Polygon.Count - 1
    for ($i = 0; $i -lt $Polygon.Count; $i++) {
        $xi = [double]$Polygon[$i][0]
        $yi = [double]$Polygon[$i][1]
        $xj = [double]$Polygon[$j][0]
        $yj = [double]$Polygon[$j][1]

        $crosses = (($yi -gt $Y) -ne ($yj -gt $Y))
        if ($crosses) {
            $xAtY = (($xj - $xi) * ($Y - $yi) / (($yj - $yi) + 0.0)) + $xi
            if ($X -lt $xAtY) { $inside = -not $inside }
        }
        $j = $i
    }
    return $inside
}

$dataPath = Join-Path $Root "data\base_analisada.csv"
$geoPath = Join-Path $Root "data\grade_espacial_df_LIMPA.geojson"
$rows = @(Import-Csv -LiteralPath $dataPath)
$geo = Get-Content -Raw -LiteralPath $geoPath | ConvertFrom-Json

# Enriquecimento das chaves usadas pela implementação atual e por uma versão canônica.
$prepared = foreach ($row in $rows) {
    $exactKey = Get-AddressKey $row
    $canonicalKey = Get-CanonicalAddressKey $row
    $lat = Get-Number $row.latitude
    $lon = Get-Number $row.longitude
    $hour = Get-Number $row.hora
    $stored = Get-Number $row.reincidencia_endereco

    [pscustomobject]@{
        Row = $row
        Numero = [string]$row.numero
        DataHora = [string]$row.'data hora'
        ExactKey = $exactKey
        CanonicalKey = $canonicalKey
        Cidade = [string]$row.cidade
        Quadra = [string]$row.quadra
        Complemento = [string]$row.complemento
        TipoMoradia = [string]$row.TIPO_MORADIA
        TipoEsperado = Get-ResidentialType $exactKey
        Latitude = $lat
        Longitude = $lon
        Hora = $hour
        StoredRecurrence = $stored
        IdCelula = $row.id_celula
    }
}

function Get-GroupCount([object[]]$Items, [string]$Property) {
    $result = @{}
    foreach ($item in $Items) {
        $key = [string]$item.$Property
        if (-not $result.ContainsKey($key)) { $result[$key] = 0 }
        $result[$key]++
    }
    return $result
}

$exactCounts = Get-GroupCount $prepared "ExactKey"
$canonicalCounts = Get-GroupCount $prepared "CanonicalKey"
$residential = @($prepared | Where-Object { $_.TipoMoradia -in @("CASA", "APARTAMENTO") })
$residentialCounts = Get-GroupCount $residential "ExactKey"
$regexResidential = @($prepared | Where-Object { $_.TipoEsperado -in @("CASA", "APARTAMENTO") })
$regexResidentialCounts = Get-GroupCount $regexResidential "ExactKey"
$coordinateGroups = @($prepared | Where-Object { $null -ne $_.Latitude -and $null -ne $_.Longitude } | Group-Object { "{0}|{1}" -f $_.Latitude, $_.Longitude } | Sort-Object Count -Descending)
$dominantCoordinateKey = if ($coordinateGroups.Count -gt 0) { $coordinateGroups[0].Name } else { "" }
$dominantCoordinateCount = if ($coordinateGroups.Count -gt 0) { $coordinateGroups[0].Count } else { 0 }

# Validação do GeoJSON e do vínculo id_celula -> polígono.
$featuresById = @{}
$duplicateGeoIds = @()
foreach ($feature in @($geo.features)) {
    $id = [string]$feature.properties.id_celula
    if ($featuresById.ContainsKey($id)) { $duplicateGeoIds += $id }
    $featuresById[$id] = $feature
}

$spatialChecks = foreach ($item in $prepared) {
    $idNum = Get-Number $item.IdCelula
    $id = if ($null -ne $idNum) { [string][int]$idNum } else { "" }
    $spatialStatus = "sem_id_celula"
    $inPolygon = $null
    $coordinateKey = if ($null -ne $item.Latitude -and $null -ne $item.Longitude) { "{0}|{1}" -f $item.Latitude, $item.Longitude } else { "" }

    if ($null -ne $item.Latitude -and $null -ne $item.Longitude -and $id -ne "") {
        if (-not $featuresById.ContainsKey($id)) {
            $spatialStatus = "id_nao_encontrado_no_geojson"
        } else {
            $feature = $featuresById[$id]
            $ring = @($feature.geometry.coordinates[0])
            $inPolygon = Test-PointInPolygon $item.Longitude $item.Latitude $ring
            $xs = @($ring | ForEach-Object { [double]$_[0] })
            $ys = @($ring | ForEach-Object { [double]$_[1] })
            $minX = ($xs | Measure-Object -Minimum).Minimum
            $maxX = ($xs | Measure-Object -Maximum).Maximum
            $minY = ($ys | Measure-Object -Minimum).Minimum
            $maxY = ($ys | Measure-Object -Maximum).Maximum
            $insideBoundingBox = $item.Longitude -ge $minX -and $item.Longitude -le $maxX -and $item.Latitude -ge $minY -and $item.Latitude -le $maxY
            $spatialStatus = if ($inPolygon) { "ok" } elseif ($insideBoundingBox) { "na_bounding_box_revisar_borda" } else { "ponto_fora_do_poligono" }
        }
    } elseif ($null -ne $item.Latitude -and $null -ne $item.Longitude) {
        $spatialStatus = if ($coordinateKey -eq $dominantCoordinateKey) { "coordenada_dominante_sem_id_celula" } else { "coordenada_valida_sem_id_celula" }
    }

    [pscustomobject]@{
        Numero = $item.Numero
        IdCelula = $item.IdCelula
        Latitude = $item.Latitude
        Longitude = $item.Longitude
        SpatialStatus = $spatialStatus
    }
}

$mismatchedStored = @($prepared | Where-Object {
    $expected = $exactCounts[$_.ExactKey]
    $null -eq $_.StoredRecurrence -or [int][math]::Round($_.StoredRecurrence) -ne $expected
})

$sameTimestampGroups = @($prepared | Group-Object { "$($_.ExactKey)|$($_.DataHora)" } | Where-Object { $_.Count -gt 1 })

$canonicalFragmentation = @($prepared | Where-Object {
    $exactCounts[$_.ExactKey] -ne $canonicalCounts[$_.CanonicalKey]
})

$typeMismatches = @($prepared | Where-Object { (Normalize-Label $_.TipoMoradia) -ne (Normalize-Label $_.TipoEsperado) })
$duplicateNumbers = @($prepared | Group-Object Numero | Where-Object { $_.Count -gt 1 })
$blankKeys = @($prepared | Where-Object { [string]::IsNullOrWhiteSpace($_.CanonicalKey) -or $_.CanonicalKey -match "^(\s+)?(\s+)?$" })
$lowInfoKeys = @($prepared | Where-Object {
    [string]::IsNullOrWhiteSpace(([string]$_.Cidade).Trim()) -or
    [string]::IsNullOrWhiteSpace(([string]$_.Quadra).Trim()) -or
    [string]::IsNullOrWhiteSpace(([string]$_.Complemento).Trim())
})

$validCoords = @($prepared | Where-Object { $null -ne $_.Latitude -and $null -ne $_.Longitude })
$zeroCoords = @($validCoords | Where-Object { $_.Latitude -eq 0 -or $_.Longitude -eq 0 })
$outOfDfCoords = @($validCoords | Where-Object {
    $_.Latitude -lt -16.3 -or $_.Latitude -gt -15.3 -or $_.Longitude -lt -48.5 -or $_.Longitude -gt -47.2
})
$invalidHour = @($prepared | Where-Object { $null -eq $_.Hora -or $_.Hora -lt 0 -or $_.Hora -gt 23 })

$expectedTurn = foreach ($item in $prepared) {
    $expected = if ($null -eq $item.Hora) { "" } elseif ($item.Hora -le 5) { "MADRUGADA" } elseif ($item.Hora -le 11) { "MANHA" } elseif ($item.Hora -le 17) { "TARDE" } else { "NOITE" }
    [pscustomobject]@{ Numero = $item.Numero; Stored = [string]$item.Row.TURNO; Expected = $expected }
}
$turnMismatches = @($expectedTurn | Where-Object { $_.Expected -ne "" -and (Normalize-Label $_.Stored) -ne $_.Expected })

# Tabela de resumo por frequência de chamados no mesmo endereço residencial.
$summary = foreach ($group in ($residential | Group-Object ExactKey | Sort-Object { [int]$_.Count })) {
    $items = @($group.Group | Sort-Object DataHora)
    $first = $items[0]
    [pscustomobject]@{
        FrequenciaChamados = [int]$group.Count
        ReincidenciasAposPrimeiro = [int]$group.Count - 1
        Cidade = $first.Cidade
        Quadra = $first.Quadra
        Complemento = $first.Complemento
        TipoMoradia = (($items | Group-Object TipoMoradia | Sort-Object Count -Descending | Select-Object -First 1).Name)
        Datas = (($items | ForEach-Object { $_.DataHora }) -join " | ")
        Numeros = (($items | ForEach-Object { $_.Numero }) -join " | ")
        IdsCelula = (($items | ForEach-Object { $_.IdCelula }) -join " | ")
        ChaveExata = $first.ExactKey
    }
}

$summary | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "reincidencia_resumo.csv")

$canonicalSummary = foreach ($group in ($residential | Group-Object CanonicalKey | Sort-Object { [int]$_.Count })) {
    $items = @($group.Group | Sort-Object DataHora)
    $first = $items[0]
    [pscustomobject]@{
        FrequenciaChamados = [int]$group.Count
        ReincidenciasAposPrimeiro = [int]$group.Count - 1
        Cidade = $first.Cidade
        Quadra = $first.Quadra
        Complemento = $first.Complemento
        TipoMoradia = (($items | Group-Object TipoMoradia | Sort-Object Count -Descending | Select-Object -First 1).Name)
        Datas = (($items | ForEach-Object { $_.DataHora }) -join " | ")
        Numeros = (($items | ForEach-Object { $_.Numero }) -join " | ")
        IdsCelula = (($items | ForEach-Object { $_.IdCelula }) -join " | ")
        ChaveNormalizada = $first.CanonicalKey
    }
}
$canonicalSummary | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "reincidencia_resumo_normalizada.csv")

$maxFrequency = if ($summary.Count -gt 0) { ($summary | Measure-Object FrequenciaChamados -Maximum).Maximum } else { 0 }
for ($frequency = 2; $frequency -le $maxFrequency; $frequency++) {
    $keys = @($summary | Where-Object { $_.FrequenciaChamados -eq $frequency } | ForEach-Object { $_.ChaveExata })
    $cases = @($residential | Where-Object { $keys -contains $_.ExactKey } | Sort-Object ExactKey, DataHora | ForEach-Object {
        [pscustomobject]@{
            FrequenciaChamados = $frequency
            ReincidenciasAposPrimeiro = $frequency - 1
            Numero = $_.Numero
            DataHora = $_.DataHora
            Cidade = $_.Cidade
            Quadra = $_.Quadra
            Complemento = $_.Complemento
            TipoMoradia = $_.TipoMoradia
            ChaveNormalizada = $_.CanonicalKey
            FrequenciaNormalizada = $canonicalCounts[$_.CanonicalKey]
            Latitude = $_.Latitude
            Longitude = $_.Longitude
            IdCelula = $_.IdCelula
            FlagAlcool = $_.Row.flag_alcool
            FlagMedidaProtetiva = $_.Row.flag_medida_protetiva
            HistoricoLimpo = $_.Row.historico_limpo
        }
    })
    $cases | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir ("casos_{0}_chamados.csv" -f $frequency))
}

$maxCanonicalFrequency = if ($canonicalSummary.Count -gt 0) { ($canonicalSummary | Measure-Object FrequenciaChamados -Maximum).Maximum } else { 0 }
for ($frequency = 2; $frequency -le $maxCanonicalFrequency; $frequency++) {
    $keys = @($canonicalSummary | Where-Object { $_.FrequenciaChamados -eq $frequency } | ForEach-Object { $_.ChaveNormalizada })
    $cases = @($residential | Where-Object { $keys -contains $_.CanonicalKey } | Sort-Object CanonicalKey, DataHora | ForEach-Object {
        [pscustomobject]@{
            FrequenciaChamados = $frequency
            ReincidenciasAposPrimeiro = $frequency - 1
            Numero = $_.Numero
            DataHora = $_.DataHora
            Cidade = $_.Cidade
            Quadra = $_.Quadra
            Complemento = $_.Complemento
            TipoMoradia = $_.TipoMoradia
            ChaveExata = $_.ExactKey
            ChaveNormalizada = $_.CanonicalKey
            FrequenciaExata = $exactCounts[$_.ExactKey]
            Latitude = $_.Latitude
            Longitude = $_.Longitude
            IdCelula = $_.IdCelula
            FlagAlcool = $_.Row.flag_alcool
            FlagMedidaProtetiva = $_.Row.flag_medida_protetiva
            HistoricoLimpo = $_.Row.historico_limpo
        }
    })
    $cases | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir ("casos_{0}_chamados_normalizado.csv" -f $frequency))
}

$spatialChecks | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "validacao_spatial_join.csv")
$prepared | Where-Object { $null -ne $_.Latitude -and $null -ne $_.Longitude -and ("{0}|{1}" -f $_.Latitude, $_.Longitude) -eq $dominantCoordinateKey } | Select-Object Numero, Cidade, Quadra, Complemento, TipoMoradia, Latitude, Longitude, IdCelula, @{Name="DominantCoordinateCount"; Expression={ $dominantCoordinateCount }} | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "alertas_coordenada_dominante.csv")
$mismatchedStored | Select-Object Numero, ExactKey, StoredRecurrence, @{Name="ExpectedRecurrence"; Expression={ $exactCounts[$_.ExactKey] }} | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "alertas_reincidencia_divergente.csv")
$sameTimestampGroups | ForEach-Object {
    $group = $_
    $group.Group | ForEach-Object {
        [pscustomobject]@{ Numero = $_.Numero; DataHora = $_.DataHora; ExactKey = $_.ExactKey; CanonicalKey = $_.CanonicalKey; HistoricoLimpo = $_.Row.historico_limpo }
    }
} | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "alertas_mesmo_endereco_datahora.csv")

$metricRows = @(
    [pscustomobject]@{ Metrica = "total_registros"; Valor = $prepared.Count; Status = "info"; Observacao = "Linhas lidas de base_analisada.csv" }
    [pscustomobject]@{ Metrica = "numeros_duplicados"; Valor = $duplicateNumbers.Count; Status = if ($duplicateNumbers.Count -eq 0) { "ok" } else { "alerta" }; Observacao = "A chave numero deveria ser única" }
    [pscustomobject]@{ Metrica = "chaves_endereco_vazias"; Valor = $blankKeys.Count; Status = if ($blankKeys.Count -eq 0) { "ok" } else { "alerta" }; Observacao = "Não devem formar grupos de reincidência" }
    [pscustomobject]@{ Metrica = "enderecos_com_componentes_ausentes"; Valor = $lowInfoKeys.Count; Status = if ($lowInfoKeys.Count -eq 0) { "ok" } else { "revisar" }; Observacao = "Cidade, quadra ou complemento ausente" }
    [pscustomobject]@{ Metrica = "recorrencia_endereco_armazenda_divergente"; Valor = $mismatchedStored.Count; Status = if ($mismatchedStored.Count -eq 0) { "ok" } else { "falha" }; Observacao = "Comparação com contagem exata cidade+quadra+complemento" }
    [pscustomobject]@{ Metrica = "grupos_mesmo_endereco_datahora"; Valor = $sameTimestampGroups.Count; Status = if ($sameTimestampGroups.Count -eq 0) { "ok" } else { "revisar" }; Observacao = "Possíveis duplicidades ou múltiplos registros do mesmo evento" }
    [pscustomobject]@{ Metrica = "fragmentacao_por_espacos"; Valor = $canonicalFragmentation.Count; Status = if ($canonicalFragmentation.Count -eq 0) { "ok" } else { "revisar" }; Observacao = "Diferença entre chave exata e chave com espaços normalizados" }
    [pscustomobject]@{ Metrica = "tipo_moradia_divergente"; Valor = $typeMismatches.Count; Status = if ($typeMismatches.Count -eq 0) { "ok" } else { "revisar" }; Observacao = "Comparação com as regex de geo_analysis.py" }
    [pscustomobject]@{ Metrica = "coordenadas_validas"; Valor = $validCoords.Count; Status = "info"; Observacao = "Latitude e longitude numéricas" }
    [pscustomobject]@{ Metrica = "coordenada_dominante"; Valor = $dominantCoordinateCount; Status = if ($dominantCoordinateCount -eq 0) { "ok" } else { "revisar" }; Observacao = "Maior coordenada repetida; o geo_analysis.py remove esse ponto antes do spatial join" }
    [pscustomobject]@{ Metrica = "coordenada_dominante_percentual"; Valor = if ($prepared.Count -gt 0) { [math]::Round(100.0 * $dominantCoordinateCount / $prepared.Count, 1) } else { 0 }; Status = if ($dominantCoordinateCount -eq 0) { "ok" } else { "revisar" }; Observacao = "Percentual dos registros no ponto dominante" }
    [pscustomobject]@{ Metrica = "coordenadas_zero"; Valor = $zeroCoords.Count; Status = if ($zeroCoords.Count -eq 0) { "ok" } else { "revisar" }; Observacao = "Coordenadas zero são removidas do spatial join" }
    [pscustomobject]@{ Metrica = "coordenadas_fora_do_envelope_df"; Valor = $outOfDfCoords.Count; Status = if ($outOfDfCoords.Count -eq 0) { "ok" } else { "alerta" }; Observacao = "Envelope amplo de controle do Distrito Federal" }
    [pscustomobject]@{ Metrica = "ids_celula_fora_do_geojson"; Valor = (@($spatialChecks | Where-Object { $_.SpatialStatus -eq "id_nao_encontrado_no_geojson" }).Count); Status = if ((@($spatialChecks | Where-Object { $_.SpatialStatus -eq "id_nao_encontrado_no_geojson" }).Count) -eq 0) { "ok" } else { "falha" }; Observacao = "Todo id_celula usado deve existir na grade" }
    [pscustomobject]@{ Metrica = "pontos_na_bounding_box_revisar_borda"; Valor = (@($spatialChecks | Where-Object { $_.SpatialStatus -eq "na_bounding_box_revisar_borda" }).Count); Status = if ((@($spatialChecks | Where-Object { $_.SpatialStatus -eq "na_bounding_box_revisar_borda" }).Count) -eq 0) { "ok" } else { "revisar" }; Observacao = "Ponto dentro do retângulo da célula, mas fora do teste poligonal por precisão/borda" }
    [pscustomobject]@{ Metrica = "pontos_fora_do_poligono"; Valor = (@($spatialChecks | Where-Object { $_.SpatialStatus -eq "ponto_fora_do_poligono" }).Count); Status = if ((@($spatialChecks | Where-Object { $_.SpatialStatus -eq "ponto_fora_do_poligono" }).Count) -eq 0) { "ok" } else { "falha" }; Observacao = "Teste ponto-polígono para cada id_celula" }
    [pscustomobject]@{ Metrica = "turnos_divergentes"; Valor = $turnMismatches.Count; Status = if ($turnMismatches.Count -eq 0) { "ok" } else { "falha" }; Observacao = "Hora comparada com as faixas de geo_analysis.py" }
    [pscustomobject]@{ Metrica = "enderecos_residenciais_reincidentes"; Valor = (@($summary | Where-Object { $_.FrequenciaChamados -gt 1 }).Count); Status = "info"; Observacao = "Definição do relatório: TIPO_MORADIA CASA/APARTAMENTO" }
    [pscustomobject]@{ Metrica = "enderecos_residenciais_reincidentes_normalizados"; Valor = (@($canonicalSummary | Where-Object { $_.FrequenciaChamados -gt 1 }).Count); Status = "info"; Observacao = "Mesmo cálculo com espaços internos normalizados" }
    [pscustomobject]@{ Metrica = "maior_frequencia_chamados"; Valor = $maxFrequency; Status = "info"; Observacao = "Maior número de chamados no mesmo endereço residencial" }
    [pscustomobject]@{ Metrica = "geojson_features"; Valor = $featuresById.Count; Status = if ($duplicateGeoIds.Count -eq 0) { "ok" } else { "falha" }; Observacao = "Features e IDs únicos da grade GeoJSON" }
)
$metricRows | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "validacao_resumo.csv")

$typeMismatches | Select-Object Numero, ExactKey, TipoMoradia, TipoEsperado | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "alertas_tipo_moradia.csv")
$canonicalFragmentation | Select-Object Numero, ExactKey, CanonicalKey | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "alertas_normalizacao_endereco.csv")
$lowInfoKeys | Select-Object Numero, ExactKey, Cidade, Quadra, Complemento, TipoMoradia, StoredRecurrence | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath (Join-Path $OutputDir "alertas_endereco_incompleto.csv")

$metricRows | Format-Table -AutoSize
Write-Output "Arquivos de validação gravados em: $OutputDir"
